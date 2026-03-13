"""
train.py

Training loop for RAG-guided Pix2Pix.

Usage:
    python train.py --data_dir ./data/edges2shoes/train --index_dir ./index --epochs 50
"""

import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.utils import save_image
from tqdm import tqdm

from eikona.model import Generator, PatchDiscriminator
from eikona.dataset import Pix2PixDataset, denorm


def train(args):
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Using device: {device}")

    os.makedirs(args.checkpoint_dir, exist_ok=True)
    os.makedirs(args.sample_dir, exist_ok=True)

    # Dataset
    dataset = Pix2PixDataset(
        data_dir=args.data_dir,
        index_dir=args.index_dir,
        size=256,
        use_rag=True,
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)

    # Models
    G = Generator(in_channels=6, out_channels=3).to(device)   # input + retrieved = 6ch
    D = PatchDiscriminator(in_channels=9).to(device)           # input + retrieved + output = 9ch

    if args.resume:
        G.load_state_dict(torch.load(args.resume, map_location=device))
        print(f"Resumed Generator from {args.resume}")

    # Optimizers
    opt_G = torch.optim.Adam(G.parameters(), lr=args.lr, betas=(0.5, 0.999))
    opt_D = torch.optim.Adam(D.parameters(), lr=args.lr, betas=(0.5, 0.999))

    # Loss functions
    bce  = nn.BCEWithLogitsLoss()
    l1   = nn.L1Loss()

    for epoch in range(1, args.epochs + 1):
        G.train(); D.train()
        loop = tqdm(loader, desc=f"Epoch {epoch}/{args.epochs}")

        for batch in loop:
            inp  = batch["input"].to(device)       # (B, 3, 256, 256)
            tgt  = batch["target"].to(device)      # (B, 3, 256, 256)
            ref  = batch["retrieved"].to(device)   # (B, 3, 256, 256)

            # Generator input = concat(input, retrieved)
            g_input = torch.cat([inp, ref], dim=1)   # (B, 6, 256, 256)

            # ---------------------------------------------------------------
            # Train Discriminator
            # ---------------------------------------------------------------
            fake = G(g_input).detach()

            # Real pair: (inp, ref, tgt)
            real_input_D = torch.cat([inp, ref, tgt],  dim=1)  # (B, 9, 256, 256)
            fake_input_D = torch.cat([inp, ref, fake], dim=1)  # (B, 9, 256, 256)

            real_pred = D(real_input_D)
            fake_pred = D(fake_input_D)

            loss_D_real = bce(real_pred, torch.ones_like(real_pred))
            loss_D_fake = bce(fake_pred, torch.zeros_like(fake_pred))
            loss_D = (loss_D_real + loss_D_fake) * 0.5

            opt_D.zero_grad()
            loss_D.backward()
            opt_D.step()

            # ---------------------------------------------------------------
            # Train Generator
            # ---------------------------------------------------------------
            fake = G(g_input)
            fake_input_D = torch.cat([inp, ref, fake], dim=1)
            pred = D(fake_input_D)

            loss_G_adv = bce(pred, torch.ones_like(pred))
            loss_G_l1  = l1(fake, tgt) * args.lambda_l1
            loss_G     = loss_G_adv + loss_G_l1

            opt_G.zero_grad()
            loss_G.backward()
            opt_G.step()

            loop.set_postfix(D=loss_D.item(), G=loss_G.item())

        # Save samples every epoch
        with torch.no_grad():
            sample = torch.cat([denorm(inp[:4]), denorm(ref[:4]), denorm(fake[:4]), denorm(tgt[:4])], dim=0)
            save_image(sample, os.path.join(args.sample_dir, f"epoch_{epoch:03d}.png"), nrow=4)

        # Save checkpoint
        if epoch % args.save_every == 0:
            torch.save(G.state_dict(), os.path.join(args.checkpoint_dir, f"G_epoch{epoch}.pth"))
            torch.save(D.state_dict(), os.path.join(args.checkpoint_dir, f"D_epoch{epoch}.pth"))
            print(f"Saved checkpoint at epoch {epoch}")

    print("Training complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir",       type=str,   default="./data/edges2shoes/train")
    parser.add_argument("--index_dir",      type=str,   default="./index")
    parser.add_argument("--checkpoint_dir", type=str,   default="./checkpoints")
    parser.add_argument("--sample_dir",     type=str,   default="./samples")
    parser.add_argument("--epochs",         type=int,   default=50)
    parser.add_argument("--batch_size",     type=int,   default=4)
    parser.add_argument("--lr",             type=float, default=2e-4)
    parser.add_argument("--lambda_l1",      type=float, default=100.0)
    parser.add_argument("--save_every",     type=int,   default=1)
    parser.add_argument("--resume",         type=str,   default=None, help="Path to checkpoint to resume from")
    args = parser.parse_args()
    train(args)
