package bootserver

import (
	"crypto/subtle"
	"encoding/json"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"sync"
	"time"
)

const TokenHeader = "X-Srxy-Installer-Token"

// Status is polled by the boot UI.
type Status struct {
	Phase       string  `json:"phase"`
	Message     string  `json:"message"`
	Progress    float64 `json:"progress"`
	Error       string  `json:"error,omitempty"`
	RedirectURL string  `json:"redirect_url,omitempty"`
	Ready       bool    `json:"ready"`
}

// State is shared between the HTTP server and bootstrap worker.
type State struct {
	mu          sync.Mutex
	token       string
	status      Status
	lastClient  time.Time
	started     time.Time
	stop        chan struct{}
	stopOnce    sync.Once
	handoffDone bool
}

func NewState(token string) *State {
	return &State{
		token:   token,
		started: time.Now(),
		stop:    make(chan struct{}),
		status: Status{
			Phase:    "starting",
			Message:  "Starting…",
			Progress: 0,
		},
	}
}

func (s *State) Stop() {
	s.stopOnce.Do(func() { close(s.stop) })
}

func (s *State) Stopped() <-chan struct{} { return s.stop }

func (s *State) MarkHandoff() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.handoffDone = true
}

func (s *State) SetStatus(phase, message string, progress float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.status.Phase = phase
	s.status.Message = message
	s.status.Progress = progress
	s.status.Error = ""
}

func (s *State) SetError(message string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.status.Phase = "error"
	s.status.Message = "Failed"
	s.status.Error = message
}

func (s *State) SetRedirect(u string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.status.Phase = "ready"
	s.status.Message = "Opening installer…"
	s.status.Progress = 1
	s.status.RedirectURL = u
	s.status.Ready = true
	s.handoffDone = true
}

func (s *State) Snapshot() Status {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.status
}

func (s *State) touch() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastClient = time.Now()
}

func (s *State) clientActivity() (started, last time.Time, handoff bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.started, s.lastClient, s.handoffDone
}

// WatchClient stops the bootstrap if the boot tab disappears before handoff.
func (s *State) WatchClient(idle, grace time.Duration) {
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-s.stop:
			return
		case <-ticker.C:
			started, last, handoff := s.clientActivity()
			if handoff {
				return
			}
			now := time.Now()
			if last.IsZero() {
				if now.Sub(started) >= grace {
					s.Stop()
					return
				}
				continue
			}
			if now.Sub(last) >= idle {
				s.Stop()
				return
			}
		}
	}
}

// Server serves the boot UI.
type Server struct {
	state  *State
	static fs.FS
	http   *http.Server
	ln     net.Listener
}

func Start(state *State, static fs.FS) (*Server, string, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, "", err
	}
	s := &Server{state: state, static: static, ln: ln}
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.FS(static))))
	mux.HandleFunc("/api/boot-status", s.handleStatus)
	mux.HandleFunc("/api/shutdown", s.handleShutdown)
	s.http = &http.Server{Handler: mux}
	go func() { _ = s.http.Serve(ln) }()
	url := "http://" + ln.Addr().String() + "/?t=" + url.QueryEscape(state.token)
	return s, url, nil
}

func (s *Server) Shutdown() {
	_ = s.http.Close()
}

func (s *Server) tokenOK(r *http.Request) bool {
	t := r.URL.Query().Get("t")
	if t == "" {
		t = r.Header.Get(TokenHeader)
	}
	return subtle.ConstantTimeCompare([]byte(t), []byte(s.state.token)) == 1
}

func (s *Server) requireToken(w http.ResponseWriter, r *http.Request) bool {
	if s.tokenOK(r) {
		s.state.touch()
		return true
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid or missing token"})
	return false
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" && r.URL.Path != "/index.html" {
		http.NotFound(w, r)
		return
	}
	if !s.requireToken(w, r) {
		return
	}
	data, err := fs.ReadFile(s.static, "index.html")
	if err != nil {
		http.Error(w, "index missing", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	_, _ = w.Write(data)
}

func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.requireToken(w, r) {
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	_ = json.NewEncoder(w).Encode(s.state.Snapshot())
}

func (s *Server) handleShutdown(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.requireToken(w, r) {
		return
	}
	// Ignore shutdown after handoff — tab navigates away to the Python UI.
	_, _, handoff := s.state.clientActivity()
	if !handoff {
		s.state.Stop()
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]bool{"ok": true})
}

// OpenBrowser opens url with the platform default browser.
func OpenBrowser(rawURL string) error {
	return openBrowser(rawURL)
}
