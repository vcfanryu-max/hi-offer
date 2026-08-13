export type ResumeVersion = {
  id: number;
  resume_id: number;
  version_number: number;
  label: string;
  original_filename: string;
  mime_type: string;
  is_current: boolean;
  created_at: string;
  warnings?: string[];
  source_type?: "text" | "file" | "image";
  parser_method?: string | null;
  ocr_used?: boolean;
  ocr_metadata?: Record<string, unknown>;
  ocr_extracted_text?: string;
};

export type Job = {
  id: number;
  company: string;
  position: string;
  source_type: "text" | "file" | "image";
  original_filename?: string | null;
  jd_text: string;
  created_at: string;
  parser_method?: string | null;
  ocr_used?: boolean;
  ocr_metadata?: Record<string, unknown>;
  ocr_extracted_text?: string;
};

export type ApiConfig = {
  provider: string;
  model: string;
  base_url: string;
  is_configured: boolean;
  key_persisted: boolean;
  updated_at?: string | null;
  message?: string;
};

export type MatchAnalysis = {
  match_score: number;
  fit_level?: "strong_fit" | "partial_fit" | "weak_fit" | "insufficient_evidence";
  summary: string;
  strong_matches: { requirement_id?: string; requirement: string; resume_evidence: string; match_type?: "direct" | "transferable"; reason: string }[];
  gaps: { requirement_id?: string; requirement: string; severity: "high" | "medium" | "low"; reason: string }[];
  keywords: string[];
  risks: string[];
};

export type HRMessage = { status?: "ready" | "needs_input"; opening?: string; self_intro?: string; fit_points?: { jd_requirement: string; resume_evidence: string; sentence: string }[]; interest?: string; availability?: string; message: string; evidence_used: string[]; missing_fields?: string[]; tone?: string };

export type ResumeAdvice = {
  fit_level?: "strong_fit" | "partial_fit" | "weak_fit" | "insufficient_evidence";
  advice_mode?: "polish" | "bridge" | "reposition" | "needs_input";
  overall_direction?: string;
  suggestions: {
    section: string;
    location: string;
    original: string;
    problem: string;
    suggestion: string;
    reason: string;
    priority: "high" | "medium" | "low";
    action_type?: "rewrite" | "reorder" | "remove" | "clarify" | "add_if_true";
    can_apply_directly?: boolean;
    needs_user_confirmation?: boolean;
  }[];
  hard_gaps?: { requirement: string; reason: string; can_fix_by_rewriting: false; recommended_next_step: string }[];
  user_input_needed?: string[];
  not_recommended_changes?: string[];
  limitations?: string[];
};

export type ValidationDebugError = {
  error_code: string;
  field_path: string;
  expected: string;
  received: unknown;
  validation_message: string;
};

export type DebugTrace = {
  module: "resume_structure" | "jd_analysis" | "match_analysis" | "hr_message" | "resume_advice";
  prompt_version: string;
  provider: string;
  model: string;
  request_id: string;
  generation_id?: number | null;
  raw_output: string;
  parsed_json?: Record<string, unknown> | null;
  normalized_json?: Record<string, unknown> | null;
  validation_errors: ValidationDebugError[];
  repair_attempted: boolean;
  repair_request_id?: string | null;
  repair_raw_output?: string | null;
  repair_parsed_json?: Record<string, unknown> | null;
  repair_normalized_json?: Record<string, unknown> | null;
  repair_validation_errors: ValidationDebugError[];
  validation_result: "pending" | "valid" | "repaired_valid" | "invalid_after_repair";
  repair_prompt_version?: string | null;
  diagnostics?: Record<string, unknown>;
};

export type Generation = {
  id: number;
  job_id: number;
  resume_version_id: number;
  resume_version_number: number;
  resume_filename: string;
  company: string;
  position: string;
  job_source_type: "text" | "file" | "image";
  job_original_filename?: string | null;
  match_status: string;
  hr_message_status: string;
  resume_advice_status: string;
  match_error?: string | null;
  hr_message_error?: string | null;
  resume_advice_error?: string | null;
  match_prompt_version: string;
  hr_prompt_version: string;
  resume_advice_prompt_version: string;
  resume_structure_prompt_version?: string | null;
  jd_analysis_prompt_version?: string | null;
  structured_repair_prompt_version?: string | null;
  prompt_versions?: Record<string, string | null>;
  provider: string;
  model: string;
  created_at: string;
  updated_at: string;
  match_result?: MatchAnalysis | null;
  hr_message?: HRMessage | null;
  resume_advice?: ResumeAdvice | null;
  jd_text?: string;
  resume_structure?: Record<string, unknown> | null;
  jd_analysis?: Record<string, unknown> | null;
  ocr_extracted_text?: { resume?: string | null; jd?: string | null };
  debug_enabled?: boolean;
  debug_traces?: DebugTrace[];
};
