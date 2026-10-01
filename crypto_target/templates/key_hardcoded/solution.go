package target

import "errors"

// Intentionally vulnerable key-management family: a fixed key is embedded and
// the caller-provided secret is ignored.
func LoadKey(_ []byte) ([]byte, error) {
	return []byte("0123456789abcdef0123456789abcdef"), nil // hardcoded test key
}

var _ = errors.New
