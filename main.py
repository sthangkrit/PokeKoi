from __future__ import print_function

from keras.layers import Input, Dense, Reshape, Flatten, Dropout
from keras.layers import BatchNormalization, Activation, ZeroPadding2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import UpSampling3D, Conv2D, Conv3D, UpSampling2D
from keras.models import Sequential, Model
from keras.optimizers import Adam
from scipy.misc import imsave as ims
import matplotlib.pyplot as plt
from PIL import Image
# import sys
# import os
import glob
import numpy as np
from keras.models import model_from_json
import util

save_epoch = 50

class DCGAN():
    def __init__(self):
        self.img_rows = 100
        self.img_cols = 100
        # for color image
        self.channels = 3

        # learning rate เราใช้ Adam optimizer ในการปรับ หาทิศทางว่าทำไงถึงลดlost 
        optimizer = Adam(0.0001, 0.5)

        # Build and compile the discriminator
        self.discriminator = self.Discriminator()
        self.discriminator.compile(loss='binary_crossentropy',
            optimizer=optimizer,
            metrics=['accuracy'])

        # Build and compile the generator
        self.generator = self.Generator()
        self.generator.compile(loss='binary_crossentropy', optimizer=optimizer)

        # ให้ noise เป็นค่าเริ่มตัน generator
        z = Input(shape=(100,))
        img = self.generator(z)
        self.discriminator.trainable = False

        # ให้image เป็นตัวต้นของ dis
        valid = self.discriminator(img)

        self.combined = Model(z, valid)
        self.combined.compile(loss='binary_crossentropy', optimizer=optimizer)

    def Generator(self):
        # 100dimention
        noise_shape = (100,)
        # เรียก class Sequential
        model = Sequential()
        # กำหนด dense layer กำหนด node ใน hidden layers 3D
        model.add(Dense(128 * 25 * 25, activation="relu", input_shape=noise_shape))
        # เปลี่ยน รูปร่าง layer
        model.add(Reshape((25, 25, 128)))
        # เพื่อปรับ Shift, Scale ให้มีขนาดเหมาะสม ไม่เล็ก ไม่ใหญ่เกินไป 
        # โดยดูเทียบจาก Mean และ Standard Deviation ของทุก Activation ใน Layer ของทั้ง Batch นั้น
        # กำหนด momentum เฉลี่ยสำหรับการเครื่องที่
        # https://www.bualabs.com/archives/2617/what-is-batchnorm-teach-batch-normalization-train-machine-learning-model-deep-convolutional-neural-network-convnet-ep-5/
        model.add(BatchNormalization(momentum=0.8))
        # สุ่มตัวอย่างภาพ 
        model.add(UpSampling2D())
        # convolution layer
        # 128 filter = คือจำนวน kernel หรือหน้ากาก ที่เราต้องการ ซึ่งค่านี้จะเท่ากับจำนวน channels ในข้อมูลที่ส่งออกจากชั้นนี้
        #   ต้องเท่ากับ shape 128
        # padding="same" ที่บังคับให้ชั้นนี้ส่งออกข้อมูลขนาดเท่าเดิม ทำได้โดยการเพิ่มขอบที่มีค่า 0
        model.add(Conv2D(128, kernel_size=3, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))
        model.add(UpSampling2D())
        model.add(Conv2D(64, kernel_size=3, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(3, kernel_size=3, padding="same"))
        model.add(Activation("tanh"))

        model.summary()

        noise = Input(shape=noise_shape)
        img = model(noise)

        return Model(noise, img)

    def Discriminator(self):

        img_shape = (self.img_rows, self.img_cols, self.channels)

        model = Sequential()

        model.add(Conv2D(32, kernel_size=3, strides=2, input_shape=img_shape, padding="same"))
        #  Activation Function = ‘LeakyRelu’
        model.add(LeakyReLU(alpha=0.2))
        # ปิด" Neuron บางตัวใน layer ไม่ให้รับส่งข้อมูล
        model.add(Dropout(0.25))
        model.add(Conv2D(64, kernel_size=3, strides=2, padding="same"))
        model.add(ZeroPadding2D(padding=((0,1),(0,1))))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(128, kernel_size=3, strides=2, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(256, kernel_size=3, strides=1, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        # แปลงข้อมูลจากภาพหลาย channel ให้เป็นเวคเตอร์ ที่เราสามารถส่งต่อให้ชั้น MLP
        model.add(Flatten())
        model.add(Dense(1, activation='sigmoid'))

        model.summary()

        img = Input(shape=img_shape)
        validity = model(img)

        return Model(img, validity)
                                    # อ่านกี่ record ก่อนปรับ W
                                    #128
    def train(self, epochs, batch_size=32):

        # Load the dataset
        X_train = util.load_data()

        # Rescale -1 to 1
        X_train = (X_train.astype(np.float32) - 127.5) / 127.5

        half_batch = int(batch_size / 2)


        for epoch in range(epochs+1):

            # Train Discriminator
            # Select a random half batch of images
            idx = np.random.randint(0, X_train.shape[0], half_batch)
            imgs = X_train[idx]

            # Sample noise and generate a half batch of new images
            noise = np.random.normal(0, 1, (half_batch, 100))
            gen_imgs = self.generator.predict(noise)

            # Train the discriminator (real classified as ones and generated as zeros)
            d_loss_real = self.discriminator.train_on_batch(imgs, np.ones((half_batch, 1)))
            d_loss_fake = self.discriminator.train_on_batch(gen_imgs, np.zeros((half_batch, 1)))
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            #  Train Generator
            noise = np.random.normal(0, 1, (batch_size, 100))

            # Train the generator (wants discriminator to mistake images as real)
            g_loss = self.combined.train_on_batch(noise, np.ones((batch_size, 1)))

            # Plot the progress
            print ("%d [D loss: %f, acc.: %.2f%%] [G loss: %f]" % (epoch, d_loss[0], 100*d_loss[1], g_loss))

            if epoch == 0:
                model_json = self.generator.to_json()
                with open("weight/generator.json", "w") as json_file:
                    json_file.write(model_json)
            # If at save interval => save generated image samples
            if epoch % save_epoch == 0:
                self.save_imgs(epoch)
                gen_name = "weight/gen_" + str(epoch) + ".h5"
                self.generator.save_weights(gen_name)

    def save_imgs(self, epoch):
        r, c = 3, 3
        noise = np.random.normal(0, 1, (r * c, 100))
        gen_imgs = self.generator.predict(noise)

        # Rescale images 0 - 1
        gen_imgs = 0.5 * gen_imgs + 0.5
        ims('output/pokemon_%d.png'%epoch, util.merge(gen_imgs,[3,3]))

    

    def test_imgs(self):
        r, c = 3, 3
        noise = np.random.normal(0, 1, (r * c, 100))

        # load json and create model
        json_file = open('weight/generator.json', 'r')
        loaded_model_json = json_file.read()
        print (loaded_model_json)
        json_file.close()
        loaded_model = model_from_json(loaded_model_json)
        weightlist = glob.glob('weight/*.h5')
        cnt = 0
        for weight in weightlist:
            # load weights into new model
            loaded_model.load_weights(weight)
            gen_imgs = self.generator.predict(noise)
            # Rescale images 0 - 1
            gen_imgs = 0.5 * gen_imgs + 0.5
            ims('output/test_pokemon_%d.png'%cnt, util.merge(gen_imgs,[3,3]))
            cnt = cnt+save_epoch




if __name__ == '__main__':
  
    dcgan = DCGAN()
    dcgan.train(epochs=3000, batch_size=32)

    dcgan.test_imgs()
