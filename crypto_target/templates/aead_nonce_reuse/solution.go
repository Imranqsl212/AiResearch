package target

import (
	"crypto/aes"
	"crypto/cipher"
	"errors"
)

// Encrypt is intentionally vulnerable for the repair benchmark: it reuses a
// deterministic all-zero nonce for every message under the key.
func Encrypt(key, plaintext, associatedData []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, gcm.NonceSize())
	return gcm.Seal(nonce, nonce, plaintext, associatedData), nil
}

func Decrypt(key, ciphertext, associatedData []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	if len(ciphertext) < gcm.NonceSize() {
		return nil, errors.New("ciphertext too short")
	}
	nonce, body := ciphertext[:gcm.NonceSize()], ciphertext[gcm.NonceSize():]
	return gcm.Open(nil, nonce, body, associatedData)
}
