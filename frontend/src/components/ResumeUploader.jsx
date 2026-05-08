import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API = "http://localhost:8000";

export default function ResumeUploader({ onUploadSuccess }) {
  const [profile, setProfile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileRef = useRef();

  useEffect(() => { fetchProfile(); }, []);

  const fetchProfile = async () => {
    try {
      const { data } = await axios.get(`${API}/api/resume`);
      setProfile(data);
    } catch (e) {}
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setError("");
    setSuccess("");

    const allowed = [".pdf", ".docx", ".txt"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!allowed.includes(ext)) {
      setError("Only .pdf, .docx, and .txt files are supported.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("File too large — maximum 5MB.");
      return;
    }

    setUploading(true);
    const form = new FormData();
    form.append("file", file);

    try {
      const { data } = await axios.post(`${API}/api/resume/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSuccess(`✓ ${data.filename} uploaded (${data.char_count.toLocaleString()} chars extracted)`);
      await fetchProfile();
      if (onUploadSuccess) onUploadSuccess();
    } catch (e) {
      setError(e.response?.data?.detail || "Upload failed — check file format.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDelete = async () => {
    try {
      await axios.delete(`${API}/api/resume`);
      setProfile(null);
      setSuccess("");
      setError("");
    } catch (e) {}
  };

  return (
    <div className="resume-uploader">
      <div className="ru-header">
        <span className="ru-title">📄 Your Resume</span>
        {profile?.uploaded && (
          <button className="ru-delete" onClick={handleDelete} title="Remove resume">✕</button>
        )}
      </div>

      {profile?.uploaded ? (
        <div className="ru-uploaded">
          <div className="ru-filename">{profile.filename}</div>
          <div className="ru-meta">{profile.char_count?.toLocaleString()} chars · {profile.uploaded_at?.slice(0,10)}</div>
          <div className="ru-preview">{profile.preview}</div>
          <button className="ru-replace" onClick={() => fileRef.current?.click()}>
            Replace resume
          </button>
        </div>
      ) : (
        <div className="ru-empty" onClick={() => fileRef.current?.click()}>
          <div className="ru-icon">📎</div>
          <div className="ru-text">
            {uploading ? "Extracting text..." : "Upload resume (.pdf or .docx)"}
          </div>
          <div className="ru-sub">AI agents will use your actual resume</div>
        </div>
      )}

      {error && <div className="ru-error">{error}</div>}
      {success && <div className="ru-success">{success}</div>}

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
    </div>
  );
}
