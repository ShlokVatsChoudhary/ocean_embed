"""TensorFlow encoder/decoder for subsurface temperature reconstruction.

Encoder  : (C, H, W) -> compact latent z (D,) + multi-scale skip features
Decoder  : (z, skips) -> (Z, H, W) temperature profile at Z standard depths
"""
from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers


class ConvBlock(layers.Layer):
    def __init__(self, cout: int, groups: int = 8):
        super().__init__()
        self.conv1 = layers.Conv2D(cout, 3, padding="same", use_bias=False)
        self.n1 = layers.GroupNormalization(groups=groups)
        self.conv2 = layers.Conv2D(cout, 3, padding="same", use_bias=False)
        self.n2 = layers.GroupNormalization(groups=groups)

    def call(self, x):
        x = tf.nn.gelu(self.n1(self.conv1(x)))
        x = tf.nn.gelu(self.n2(self.conv2(x)))
        return x


class Encoder(layers.Layer):
    """CNN embedding engine: produces a global latent code + skips."""

    def __init__(self, widths=(24, 48, 96, 192), D: int = 256):
        super().__init__()
        self.stem = ConvBlock(widths[0])
        self.downs = [
            tf.keras.Sequential([layers.MaxPool2D(2), ConvBlock(w)])
            for w in widths[1:]
        ]
        self.attn = layers.Dense(1)
        self.proj = layers.Dense(D)
        self.D = D
        self.widths = widths

    def call(self, x):
        skips = [self.stem(x)]
        for d in self.downs:
            skips.append(d(skips[-1]))
        h = skips[-1]
        b = tf.shape(h)[0]
        c = h.shape[-1]
        flat = tf.reshape(h, [b, -1, c])                 # (B, N, C)
        mean = tf.reduce_mean(flat, 1, keepdims=True)    # (B, 1, C)
        mean = tf.broadcast_to(mean, tf.shape(flat))      # (B, N, C)
        ctx = tf.concat([mean, flat], -1)                # (B, N, 2C)
        w = tf.nn.softmax(self.attn(ctx), axis=1)        # (B, N, 1)
        z = tf.reduce_sum(flat * w, axis=1)              # (B, C)
        return self.proj(z), skips


class Decoder(layers.Layer):
    """Per-pixel depth decoder: fuses global z with skips -> (Z, H, W)."""

    def __init__(self, widths=(24, 48, 96, 192), D: int = 256, Z: int = 15):
        super().__init__()
        rev = list(reversed(widths))                     # deep -> shallow
        self.up = [layers.Conv2DTranspose(rev[i + 1], 3, strides=2,
                                          padding="same")
                   for i in range(len(rev) - 1)]
        self.conv = [ConvBlock(rev[i + 1]) for i in range(len(rev) - 1)]
        self.head = layers.Conv2D(Z, 1)
        self.D = D
        self.Z = Z
        self.rev = rev

    def call(self, inputs):
        z, skips = inputs
        w_list = list(reversed(skips))                   # deep -> shallow
        x = w_list[0]
        for i, up in enumerate(self.up):
            x = up(x)
            skip = w_list[i + 1]
            if x.shape[1] != skip.shape[1] or x.shape[2] != skip.shape[2]:
                x = tf.image.resize(x, [tf.shape(skip)[1], tf.shape(skip)[2]])
            zc = tf.reshape(z, [tf.shape(z)[0], 1, 1, tf.shape(z)[-1]])
            zc = tf.tile(zc, [1, tf.shape(x)[1], tf.shape(x)[2], 1])
            x = tf.concat([x, skip, zc], -1)
            x = self.conv[i](x)
        return self.head(x)                              # (B, H, W, Z)


class OceanModel(tf.keras.Model):
    """Encoder + decoder with a masked, depth-weighted training step.

    The project convention is channels-first (B, C, H, W); Keras conv layers
    are channels-last, so we transpose at the model boundary.
    """

    def __init__(self, cin: int = 4, D: int = 256, Z: int = 15,
                 widths=(24, 48, 96, 192), deep_weight: float = 2.5):
        super().__init__()
        self.enc = Encoder(widths=widths, D=D)
        self.dec = Decoder(widths=widths, D=D, Z=Z)
        self.Z = Z
        # deeper levels get more weight (harder, larger variance)
        self.depth_w = tf.constant(
            tf.linspace(1.0, deep_weight, Z), dtype=tf.float32)

    def call(self, x, training=False):
        xh = tf.transpose(x, [0, 2, 3, 1])            # (B,C,H,W)->(B,H,W,C)
        z, skips = self.enc(xh)
        out = self.dec((z, skips))                    # (B,H,W,Z)
        return tf.transpose(out, [0, 3, 1, 2]), z    # -> (B,Z,H,W)

    def masked_loss(self, y_true, y_pred, mask):
        w = self.depth_w[None, :, None, None]
        err = tf.square(y_pred - y_true) * mask * w
        return tf.reduce_sum(err) / (tf.reduce_sum(mask * w) + 1e-6)

    def train_step(self, data):
        x, y, mask = data
        with tf.GradientTape() as tape:
            pred, _ = self(x, training=True)
            loss = self.masked_loss(y, pred, mask)
        grads = tape.gradient(loss, self.trainable_variables)
        self.optimizer.apply_gradients(zip(grads, self.trainable_variables))
        return {"loss": loss}

    def test_step(self, data):
        x, y, mask = data
        pred, _ = self(x, training=False)
        return {"loss": self.masked_loss(y, pred, mask)}
