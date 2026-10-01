package target

import "errors"

func LoadKey(secret []byte) ([]byte, error) {
	if len(secret) != 32 { return nil, errors.New("key must be 32 bytes") }
	key := append([]byte(nil), secret...)
	return key, nil
}
