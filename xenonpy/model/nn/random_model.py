# Copyright 2018 TsumiNa. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from collections import namedtuple

from torch import nn

from .layer1 import Layer1d
from .wrap import L1
from ...utils import Product


class Generator1d(object):
    """
    Generate random model from the supplied parameters.
    """

    def __init__(self, n_features: int, n_predict: int, *,
                 n_neuron,
                 p_drop=(0.0,),
                 layer_func=(L1.linear(),),
                 act_func=(nn.ReLU(),),
                 batch_normalize=(L1.batch_norm(),)
                 ):
        """
        Parameters
        ----------
        n_features: int
            Input dimension.
        n_predict: int
            Output dimension.
        n_neuron: [int]
            Number of neuron.
        p_drop: [float]
            Dropout rate.
        layer_func: [func]
            Layer functions. such like: :meth:`~.L1.linear`.
        act_func: [func]
            Activation functions. such like: :class:`torch.nn.ReLU`.
        batch_normalize: [bool]
            Batch Normalization. such like: :meth:`~.L1.batch_norm`.
        """
        self.n_in, self.n_out = n_features, n_predict

        # save parameters
        self.n_neuron = n_neuron
        self.p_drop = p_drop
        self.layer_func = layer_func
        self.act_func = act_func
        self.batch_normalize = batch_normalize

        # calculate layer's variety
        self.layer_var = Product(n_neuron, p_drop, layer_func, act_func, batch_normalize)

    def __call__(self, hidden: int, *, n_models: int = 0, scheduler=None, replace=False):
        """
        Generate sample model.

        Parameters
        ----------
        hidden: int
            Number of hidden layers.
        n_models: int
            Number of model sample
        scheduler: func
            A function be used to determining the layer parameters from previous layer.

            .. py:function:: scheduler(index, paras) -> dict

                index: int
                    Index of  current layer.
                paras: dict
                    Layer parameters Include:
                    ``n_in``, ``n_out``, ``p_drop``, ``layer_func``, ``act_func``, ``batch_nor``.
                return: dict
                    Layer parameters as dict.

        Returns
        -------
        iterable
            Random models as generator.
            Can be access with :func:`next()` or ``for ... in models`` statement.

        Examples
        --------
        >>> from  math import ceil
        >>> from random import uniform
        >>> scheduler = lambda index, pars: dict(paras, n_out=ceil(paras['n_out'] * uniform(0.5, 0.8)))
        """
        from numpy.random import choice
        named_paras = ['n_in', 'n_out', 'p_drop', 'layer_func', 'act_func', 'batch_nor']
        layer = namedtuple('LayerParas', named_paras)

        if scheduler is None:
            all_ = Product(self.layer_var, repeat=hidden)
            all_size = self.layer_var.size ** hidden

            if n_models == 0:
                n_models = all_size
            if n_models > all_size and not replace:
                raise ValueError("larger sample than population({}) when 'replace=False'".format(all_size))

            # sampling all_
            samples = choice(all_size, n_models, replace).tolist()
            while True:
                try:
                    i = samples.pop()
                    layer_paras = all_[i]
                except IndexError:
                    raise StopIteration()

                # set layers
                layers = list()
                n_in = self.n_in
                sig = [n_in]
                for para in layer_paras:
                    layer_ = layer(*((n_in,) + para))._asdict()
                    layers.append(Layer1d(**layer_))
                    n_in = para[0]
                    sig.append(n_in)
                sig.append(self.n_out)
                out_layer = Layer1d(n_in=n_in, n_out=self.n_out, act_func=None, batch_nor=None, p_drop=0)
                layers.append(out_layer)

                model = nn.Sequential(*layers)
                setattr(model, 'sig', '-'.join(map(str, sig)))
                yield model

        else:
            if n_models == 0:
                n_models = self.layer_var.size
            if n_models > self.layer_var.size and not replace:
                raise ValueError("larger sample than population({}) when 'replace=False'".format(self.layer_var.size))

            samples = choice(self.layer_var.size, n_models, replace).tolist()

            while True:
                try:
                    i = samples.pop()
                except IndexError:
                    raise StopIteration()

                layers = list()
                n_in = self.n_in
                sig = [n_in]
                paras = self.layer_var[i]
                layer_ = layer(*((n_in,) + paras))._asdict()

                layers.append(Layer1d(**layer_))
                n_in = layer_['n_out']
                for n in range(hidden - 1):
                    layer_ = scheduler(n + 1, layer_)
                    layer_['n_in'] = n_in
                    layers.append(Layer1d(**layer_))
                    n_in = layer_['n_out']
                    sig.append(n_in)
                sig.append(self.n_out)
                out_layer = Layer1d(n_in=n_in, n_out=self.n_out, act_func=None, batch_nor=None, p_drop=0)
                layers.append(out_layer)

                model = nn.Sequential(*layers)
                setattr(model, 'sig', '-'.join(map(str, sig)))
                yield model
