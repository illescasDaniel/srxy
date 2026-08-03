package fetch

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// DownloadHTTPS downloads url to destPath, verifying sha256Hex when non-empty.
func DownloadHTTPS(url, destPath, sha256Hex string, onProgress func(done, total int64)) error {
	if !strings.HasPrefix(url, "https://") {
		return fmt.Errorf("refusing non-HTTPS URL")
	}
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return err
	}
	tmp := destPath + ".partial"
	_ = os.Remove(tmp)

	resp, err := http.Get(url) //nolint:gosec // URL is pinned in bootstrap meta
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download %s: HTTP %s", url, resp.Status)
	}

	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	hasher := sha256.New()
	writer := io.MultiWriter(f, hasher)

	total := resp.ContentLength
	var done int64
	buf := make([]byte, 32*1024)
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, werr := writer.Write(buf[:n]); werr != nil {
				f.Close()
				_ = os.Remove(tmp)
				return werr
			}
			done += int64(n)
			if onProgress != nil {
				onProgress(done, total)
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			f.Close()
			_ = os.Remove(tmp)
			return readErr
		}
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		return err
	}

	got := hex.EncodeToString(hasher.Sum(nil))
	want := strings.ToLower(strings.TrimSpace(sha256Hex))
	if want == "" {
		allow := os.Getenv("SRXY_INSTALLER_ALLOW_UNVERIFIED") == "1"
		if !allow {
			_ = os.Remove(tmp)
			return fmt.Errorf("empty sha256 refused (set SRXY_INSTALLER_ALLOW_UNVERIFIED=1 for dev)")
		}
	} else if got != want {
		_ = os.Remove(tmp)
		return fmt.Errorf("sha256 mismatch for %s: got %s want %s", url, got, want)
	}

	_ = os.Remove(destPath)
	return os.Rename(tmp, destPath)
}

// FileSHA256 returns the hex digest of path.
func FileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
