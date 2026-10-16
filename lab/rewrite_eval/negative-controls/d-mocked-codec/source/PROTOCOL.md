# Session envelope v1

The credential is `base64url(UTF-8 user ID).base64url(HMAC-SHA256(key, encoded ID))`, without padding.
The verifier returns the decoded ID only after signature verification. Changing the payload without recomputing its signature must return invalid.
The evaluation uses only a synthetic key and credentials. No Rails cookie, browser UI, or database is required by this protocol.
