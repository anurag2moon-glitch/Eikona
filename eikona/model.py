"""
eikona/model.py

U-Net Generator and 70x70 PatchGAN Discriminator for RAG-guided Pix2Pix.
"""

import torch
import torch.nn as nn


class UNetBlock(nn.Module):
    def __init__(self, in_channels, out_channels, down=True, bn=True, dropout=False, relu=True):
        super().__init__()
        layers = []
        if down:
            layers.append(nn.Conv2d(in_channels, out_channels, 4, 2, 1, bias=False))
        else:
            layers.append(nn.ConvTranspose2d(in_channels, out_channels, 4, 2, 1, bias=False))
        if bn:
            layers.append(nn.BatchNorm2d(out_channels))
        if relu:
            layers.append(nn.ReLU(inplace=True) if not down else nn.LeakyReLU(0.2, inplace=True))
        if dropout:
            layers.append(nn.Dropout(0.5))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)


class Generator(nn.Module):
    """
    U-Net generator.
    Input: 6-channel image (3 input + 3 retrieved reference)
    Output: 3-channel translated image
    """
    def __init__(self, in_channels=6, out_channels=3, features=64):
        super().__init__()

        # Encoder
        self.enc1 = nn.Sequential(nn.Conv2d(in_channels, features, 4, 2, 1), nn.LeakyReLU(0.2))  # 128
        self.enc2 = UNetBlock(features,     features * 2,  down=True)   # 64
        self.enc3 = UNetBlock(features * 2, features * 4,  down=True)   # 32
        self.enc4 = UNetBlock(features * 4, features * 8,  down=True)   # 16
        self.enc5 = UNetBlock(features * 8, features * 8,  down=True)   # 8
        self.enc6 = UNetBlock(features * 8, features * 8,  down=True)   # 4
        self.enc7 = UNetBlock(features * 8, features * 8,  down=True)   # 2
        self.bottleneck = nn.Sequential(nn.Conv2d(features * 8, features * 8, 4, 2, 1), nn.ReLU())  # 1

        # Decoder (input channels doubled due to skip connections)
        self.dec1 = UNetBlock(features * 8,      features * 8, down=False, dropout=True)
        self.dec2 = UNetBlock(features * 8 * 2,  features * 8, down=False, dropout=True)
        self.dec3 = UNetBlock(features * 8 * 2,  features * 8, down=False, dropout=True)
        self.dec4 = UNetBlock(features * 8 * 2,  features * 8, down=False)
        self.dec5 = UNetBlock(features * 8 * 2,  features * 4, down=False)
        self.dec6 = UNetBlock(features * 4 * 2,  features * 2, down=False)
        self.dec7 = UNetBlock(features * 2 * 2,  features,     down=False)
        self.final = nn.Sequential(
            nn.ConvTranspose2d(features * 2, out_channels, 4, 2, 1),
            nn.Tanh()
        )

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        e5 = self.enc5(e4)
        e6 = self.enc6(e5)
        e7 = self.enc7(e6)
        b  = self.bottleneck(e7)

        d1 = self.dec1(b)
        d2 = self.dec2(torch.cat([d1, e7], dim=1))
        d3 = self.dec3(torch.cat([d2, e6], dim=1))
        d4 = self.dec4(torch.cat([d3, e5], dim=1))
        d5 = self.dec5(torch.cat([d4, e4], dim=1))
        d6 = self.dec6(torch.cat([d5, e3], dim=1))
        d7 = self.dec7(torch.cat([d6, e2], dim=1))
        return self.final(torch.cat([d7, e1], dim=1))


class PatchDiscriminator(nn.Module):
    """
    70x70 PatchGAN discriminator.
    Input: concatenated (input_image + retrieved_ref + real_or_fake_output) = 9 channels
    """
    def __init__(self, in_channels=9, features=64):
        super().__init__()
        self.model = nn.Sequential(
            nn.Conv2d(in_channels, features, 4, 2, 1),
            nn.LeakyReLU(0.2),
            nn.Conv2d(features,     features * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(features * 2),
            nn.LeakyReLU(0.2),
            nn.Conv2d(features * 2, features * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(features * 4),
            nn.LeakyReLU(0.2),
            nn.Conv2d(features * 4, features * 8, 4, 1, 1, bias=False),
            nn.BatchNorm2d(features * 8),
            nn.LeakyReLU(0.2),
            nn.Conv2d(features * 8, 1, 4, 1, 1),  # output patch predictions
        )

    def forward(self, x):
        return self.model(x)
