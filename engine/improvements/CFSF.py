import torch
import torch.nn as nn


__all__ = ['CFSFModule', 'SpatialWeights', 'ChannelWeights']





class SpatialWeights(nn.Module):
    def __init__(self, dim=None, reduction=1):
        super(SpatialWeights, self).__init__()
        self.dim = dim
        self.conv = nn.Conv2d(1, 2, kernel_size=1, bias=True)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x1, x2):
        B, _, H, W = x1.shape
        x = torch.cat((x1, x2), dim=1)  # B 2C H W

        x = torch.mean(x, dim=1, keepdim=True)  # B 1 H W
        a = self.softmax(self.conv(x))  # B 2 H W

        a1, a2 = a[:, 0:1, :, :], a[:, 1:2, :, :]  # B 1 H W
        f1 = x1 * a1
        f2 = x2 * a2
        return f1, f2



class ChannelWeights(nn.Module):
    def __init__(self, dim=None, reduction=1, act_layer=nn.ReLU):
        super(ChannelWeights, self).__init__()
        self.dim = dim  # kept for backward compatibility
        self.reduction = reduction  # unused; kept for backward compatibility
        self.act_layer = act_layer  # unused; kept for backward compatibility
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)

        self.conv = None
        self.softmax = nn.Softmax(dim=1)
        self._in_channels = None

    def forward(self, x1, x2):
        # x1/x2 -> concat -> avg/max pool (H,W -> 1) -> concat -> conv -> softmax -> b1/b2
        b, c1, _, _ = x1.shape
        c2 = x2.shape[1]
        x = torch.cat((x1, x2), dim=1)  # B (C1+C2) H W


        pooled_avg = self.avg_pool(x)  # B (C1+C2) 1 1

        pooled_max = self.max_pool(x)  # B (C1+C2) 1 1

        pooled = torch.cat((pooled_avg, pooled_max), dim=1)  # B 2*(C1+C2) 1 1


        in_channels = pooled.shape[1]
        if self.conv is None:
            self._in_channels = in_channels
            self.conv = nn.Conv2d(in_channels, in_channels//2, kernel_size=1, bias=True).to(device=x1.device, dtype=x1.dtype)
        elif in_channels != self._in_channels:
            raise ValueError(
                f'ChannelWeights was initialized on in_channels={self._in_channels}, got in_channels={in_channels}.'
            )


        logits = self.conv(pooled)  # B (C1+C2) 1 1 == B (2*C) 1 1 when C1==C2==C
        beta = logits.view(b, 2, c1, 1, 1)  # B 2 C 1 1
        beta = self.softmax(beta)  # softmax over the 2 branches, per channel
        b1, b2 = beta[:, 0, :, :, :], beta[:, 1, :, :, :]  # B C 1 1


        y1 = x1 * b1
        y2 = x2 * b2


        return y1, y2



class CFSFModule(nn.Module):
    def __init__(self, dim=None, reduction=1):
        super().__init__()
        # dim is unused when C differs; kept for compatibility with older checkpoints/configs.
        self.dim = dim
        self.reduction = reduction
        self.spatial_weights = SpatialWeights(dim=dim, reduction=reduction)
        self.channel_weights = ChannelWeights(dim=dim, reduction=reduction)

    def forward(self, x1, x2):
        if x1.dim() != 4:
            raise ValueError(f'CFSFModule expects 4D tensors (B,C,H,W), got x1.dim()={x1.dim()}')
        if x2.dim() != 4:
            raise ValueError(f'CFSFModule expects 4D tensors (B,C,H,W), got x2.dim()={x2.dim()}')
        if x1.shape[0] != x2.shape[0] or x1.shape[2:] != x2.shape[2:]:
            raise ValueError(
                f'CFSFModule expects x1 and x2 to share B,H,W, got {tuple(x1.shape)} vs {tuple(x2.shape)}'
            )

        x1, x2 = self.spatial_weights(x1, x2)
        y1, y2 = self.channel_weights(x1, x2)
        return y1 + y2



if __name__ == '__main__':
    block = CFSFModule()

    left = torch.randn(2, 256, 64, 64)
    right = torch.randn(2, 256, 64, 64)

    print("input:", left.shape, right.shape)
    out = block(left, right)
    print("output:", out.shape)
