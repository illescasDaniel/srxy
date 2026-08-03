package fetch

import "testing"

func TestDownloadHTTPS_RejectsHTTP(t *testing.T) {
	err := DownloadHTTPS("http://example.com/x", t.TempDir()+"/x", "abc", nil)
	if err == nil {
		t.Fatal("expected error for non-HTTPS URL")
	}
}
