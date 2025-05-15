# crypto_utils.py
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


def generate_key_pair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def serialize_public_key(pubkey: rsa.RSAPublicKey) -> str:
    return pubkey.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

def deserialize_public_key(pub_pem: str) -> rsa.RSAPublicKey:
    return serialization.load_pem_public_key(pub_pem.encode())


def encrypt_message(pubkey, plaintext: str) -> bytes:
    return pubkey.encrypt(
        plaintext.encode(),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                     algorithm=hashes.SHA256(),
                     label=None)
    )

def decrypt_message(privkey, ciphertext: bytes) -> str:
    return privkey.decrypt(
        ciphertext,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                     algorithm=hashes.SHA256(),
                     label=None)
    ).decode()
