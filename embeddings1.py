import numpy as np

emb = np.load("j_voiceprint2.npy")

print("Shape:", emb.shape)      # should be (192,)
print("First 10 values:", emb[:10])

