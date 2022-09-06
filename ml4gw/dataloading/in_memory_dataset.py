import itertools
from typing import Optional

import numpy as np
import torch

from ml4gw.utils.slicing import slice_kernels


class InMemoryDataset:
    def __init__(
        self,
        X: np.ndarray,
        kernel_size: int,
        y: Optional[np.ndarray] = None,
        batch_size: int = 32,
        stride: int = 1,
        batches_per_epoch: Optional[int] = None,
        coincident: bool = True,
        shuffle: bool = True,
        device: str = "cpu",
    ) -> None:
        self.X = torch.Tensor(X).to(device)
        if y is not None:
            self.y = torch.Tensor(y).to(device)
        else:
            self.y = None

        self.kernel_size = kernel_size
        self.batch_size = batch_size
        self.batches_per_epoch = batches_per_epoch
        self.stride = stride
        self.shuffle = shuffle
        self.coincident = coincident

    @property
    def num_kernels(self) -> int:
        return (self.X.shape[-1] - self.kernel_size) // self.stride + 1

    def __len__(self) -> int:
        if self.batches_per_epoch is not None:
            return self.batches_per_epoch

        if self.coincident:
            return (self.num_kernels - 1) // self.batch_size + 1
        else:
            power = len(self.X)
            if self.y is not None:
                power += 1
            num_kernels = self.num_kernels**power
            return (num_kernels - 1) // self.batch_size + 1

    def __iter__(self) -> None:
        if not self.coincident:
            idx = [np.arange(self.num_kernels) for _ in range(len(self.X))]
            if self.y is not None:
                idx.append(np.arange(self.num_kernels))
            idx = np.stack(itertools.product(*idx))

            if self.shuffle:
                perm_idx = np.random.permutation(len(idx))
                idx = idx[perm_idx]

            self._idx = torch.Tensor(idx)
        elif self.shuffle:
            self._idx = torch.randperm(self.num_kernels)
        else:
            self._idx = torch.arange(len(self))

        self._i = 0

    def __next__(self):
        if self._i >= len(self):
            raise StopIteration

        slc = slice(self._i * self.batch_size, (self._i + 1) * self.batch_size)
        idx = self._idx[slc] * self.stride

        if not self.coincident and self.y is not None:
            y = slice_kernels(self.y, self._idx[:, -1])
            idx = idx[:, :-1]
        elif y is not None:
            y = slice_kernels(self.y, idx)

        X = slice_kernels(self.X, idx)
        self._i += 1

        if self.y is not None:
            return X, y
        return X