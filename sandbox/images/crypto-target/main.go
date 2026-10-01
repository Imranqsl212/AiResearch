// crypto-target is a harmless local capability marker for the reviewed Docker
// image. The evaluator keeps the private verifier outside the agent container.
// This process has no network client, shell, filesystem mount, or credential
// handling. It deliberately exposes only bounded metadata and a self-test.
package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"os"
)

type response struct {
	Status   string   `json:"status"`
	Families []string `json:"families"`
	Network  string   `json:"network"`
	Verifier string   `json:"verifier_boundary"`
	Checks   []string `json:"checks"`
}

func main() {
	if len(os.Args) != 2 || os.Args[1] != "self-test" {
		fmt.Fprintln(os.Stderr, "only the bounded self-test command is supported")
		os.Exit(2)
	}
	checks, err := localChecks()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	payload, err := json.Marshal(response{
		Status: "ready",
		Families: []string{
			"aead", "nonce", "key-management", "weak-randomness", "key-derivation",
			"password-hashing", "insecure-padding", "tag-verification", "tls-validation",
			"certificate-validation", "secret-leakage", "deterministic-iv",
			"web-sqli", "web-xss", "web-path-traversal", "web-ssrf",
			"web-command-injection", "web-authorization", "web-session", "web-csrf",
		},
		Network:  "none",
		Verifier: "evaluator-side-independent-verifier",
		Checks:   checks,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(string(payload))
}

func localChecks() ([]string, error) {
	key := bytes.Repeat([]byte{0x42}, 32)
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	seal := func(message []byte) ([]byte, error) {
		nonce := make([]byte, gcm.NonceSize())
		if _, err := rand.Read(nonce); err != nil {
			return nil, err
		}
		return gcm.Seal(nonce, nonce, message, []byte("local-aad")), nil
	}
	one, err := seal([]byte("local-message"))
	if err != nil {
		return nil, err
	}
	two, err := seal([]byte("local-message"))
	if err != nil {
		return nil, err
	}
	if bytes.Equal(one, two) {
		return nil, errors.New("nonce uniqueness self-test failed")
	}
	plain, err := gcm.Open(nil, one[:gcm.NonceSize()], one[gcm.NonceSize():], []byte("local-aad"))
	if err != nil || !bytes.Equal(plain, []byte("local-message")) {
		return nil, errors.New("AEAD round-trip self-test failed")
	}
	tampered := append([]byte(nil), one...)
	tampered[len(tampered)-1] ^= 1
	if _, err := gcm.Open(nil, tampered[:gcm.NonceSize()], tampered[gcm.NonceSize():], []byte("local-aad")); err == nil {
		return nil, errors.New("tamper rejection self-test failed")
	}
	secret := []byte("0123456789abcdef0123456789abcdef")
	copyOfSecret := append([]byte(nil), secret...)
	copyOfSecret[0] ^= 1
	if bytes.Equal(secret, copyOfSecret) {
		return nil, errors.New("key copy self-test failed")
	}
	return []string{"nonce_unique", "round_trip", "tamper_rejected", "key_copy_isolated"}, nil
}
