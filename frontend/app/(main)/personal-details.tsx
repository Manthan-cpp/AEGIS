"use client";

import { useState, useEffect } from "react";
import { Save, Check } from "lucide-react";

export function PersonalDetailsForm() {
  const [isLoaded, setIsLoaded] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    age: "",
    anonymousName: "",
    emergencyContact: "",
    medicalNotes: "",
  });
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success">("idle");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = localStorage.getItem("aegis-personal-details");
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setFormData((prev) => ({ ...prev, ...parsed }));
        } catch {
          console.error("Failed to parse personal details from localStorage");
        }
      }
      setIsLoaded(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    if (saveStatus !== "idle") setSaveStatus("idle");
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveStatus("saving");
    
    // Hardcode save to localStorage to persist across refreshes
    localStorage.setItem("aegis-personal-details", JSON.stringify(formData));
    
    setTimeout(() => {
      setSaveStatus("success");
    }, 400); // Small delay to show saving state visually
  };

  if (!isLoaded) return <div style={{ padding: "20px" }}>Loading personal details...</div>;

  return (
    <div style={{ padding: "16px 20px" }}>
      <div style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "20px", fontWeight: 600, color: "#2c3955", margin: "0 0 8px 0" }}>Personal Details</h2>
        <p style={{ fontSize: "13px", color: "#77849b", margin: 0 }}>
          This information is stored locally on your device for your safety. It helps Aegis tailor its support to you.
        </p>
      </div>

      <form onSubmit={handleSave} className="sos-form">
        <div className="sos-input-group">
          <label htmlFor="name" className="sos-label">Full Name (Optional)</label>
          <input
            id="name"
            name="name"
            type="text"
            className="sos-input"
            placeholder="e.g. Jane Doe"
            value={formData.name}
            onChange={handleChange}
          />
        </div>

        <div className="sos-input-group">
          <label htmlFor="anonymousName" className="sos-label">Anonymous Alias / Display Name</label>
          <input
            id="anonymousName"
            name="anonymousName"
            type="text"
            className="sos-input"
            placeholder="e.g. Phoenix"
            value={formData.anonymousName}
            onChange={handleChange}
          />
        </div>

        <div className="sos-input-group">
          <label htmlFor="age" className="sos-label">Age</label>
          <input
            id="age"
            name="age"
            type="number"
            className="sos-input"
            placeholder="e.g. 28"
            value={formData.age}
            onChange={handleChange}
          />
        </div>

        <div className="sos-input-group">
          <label htmlFor="emergencyContact" className="sos-label">Emergency Contact Number</label>
          <input
            id="emergencyContact"
            name="emergencyContact"
            type="tel"
            className="sos-input"
            placeholder="e.g. +91 9876543210"
            value={formData.emergencyContact}
            onChange={handleChange}
          />
        </div>

        <div className="sos-input-group">
          <label htmlFor="medicalNotes" className="sos-label">Health / Medical Notes</label>
          <textarea
            id="medicalNotes"
            name="medicalNotes"
            className="sos-textarea"
            placeholder="Any allergies, current medications, or specific conditions."
            rows={3}
            value={formData.medicalNotes}
            onChange={handleChange}
          />
        </div>

        <button 
          type="submit" 
          className="sos-primary-button" 
          style={{ width: "100%", padding: "12px 16px", marginTop: "10px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
          disabled={saveStatus === "saving"}
        >
          {saveStatus === "saving" ? (
            "Saving..."
          ) : (
            <>
              <Save size={14} aria-hidden="true" />
              <span>Save Details</span>
            </>
          )}
        </button>

        {saveStatus === "success" && (
          <div className="sos-success" role="alert" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Check size={14} aria-hidden="true" />
            <span><strong>Saved securely.</strong> Your details have been stored on this device.</span>
          </div>
        )}
      </form>
    </div>
  );
}
