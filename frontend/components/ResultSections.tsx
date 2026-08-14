"use client";

import { downloadUrl } from "@/lib/api";
import { formatAdvice, formatMatch } from "@/lib/format";
import type { Generation } from "@/lib/types";
import { TextActionBar } from "./TextActionBar";
import { DebugPanel } from "./DebugPanel";

const priority = { high: "高", medium: "中", low: "低" } as const;

function ModuleError({ message, retry, busy }: { message: string; retry: () => void; busy: boolean }) {
  return (
    <div className="module-error" role="alert">
      <p>{message}</p>
      <button className="text-button" onClick={retry} disabled={busy}>
        {busy ? "正在重试…" : "重新生成"}
      </button>
    </div>
  );
}

export function ResultSections({
  generation,
  retrying,
  onRetry,
  demo = false,
}: {
  generation: Generation;
  retrying: string | null;
  onRetry: (module: "match" | "hr-message" | "resume-advice") => void;
  demo?: boolean;
}) {
  const matchText = generation.match_result ? formatMatch(generation.match_result) : "";
  const adviceText = generation.resume_advice ? formatAdvice(generation.resume_advice, generation) : "";

  return (
    <section className="results" aria-label="生成结果">
      <div className="result-heading">
        <span>{demo ? "虚构示例数据 · 预生成结果" : "生成完成后，结果会自动保存到用户档案"}</span>
        <span className="snapshot-id">SNAPSHOT #{generation.id}</span>
      </div>

      {generation.match_result ? (
        <article className="match-summary">
          <div className="match-score" aria-label={`匹配参考分 ${generation.match_result.match_score}`}>
            <strong>{generation.match_result.match_score}</strong>
            <span>匹配参考</span>
          </div>
          <div className="match-copy">
            <p>{generation.match_result.summary}</p>
            {generation.match_result.fit_level && <span className="mini-label">FIT · {generation.match_result.fit_level}</span>}
            <div className="match-columns">
              <div>
                <h3>最强匹配</h3>
                <ul>{generation.match_result.strong_matches.slice(0, 3).map((item) => <li key={item.requirement}>{item.requirement}</li>)}</ul>
              </div>
              <div>
                <h3>关键缺口</h3>
                <ul>{generation.match_result.gaps.slice(0, 3).map((item) => <li key={item.requirement}>{item.requirement}</li>)}</ul>
              </div>
            </div>
          </div>
          <TextActionBar text={matchText} filename={`Hi_Offer_Match_${generation.id}.md`} mime="text/markdown;charset=utf-8" />
        </article>
      ) : (
        <ModuleError message={generation.match_error || "匹配分析尚未完成。"} retry={() => onRetry("match")} busy={retrying === "match"} />
      )}

      <article className="result-panel hr-panel">
        <header className="panel-heading">
          <div><h2>生成话术</h2><span>HR MESSAGE</span></div>
          {generation.hr_message && <TextActionBar text={generation.hr_message.message} filename={`Hi_Offer_HR_Message_${generation.id}.txt`} />}
        </header>
        {generation.hr_message ? (
          <p className="hr-message">{generation.hr_message.message}</p>
        ) : (
          <ModuleError message={generation.hr_message_error || "话术尚未生成。"} retry={() => onRetry("hr-message")} busy={retrying === "hr-message"} />
        )}
      </article>

      <article className="result-panel advice-panel">
        <header className="panel-heading">
          <div><h2>修改意见</h2><span>RESUME ADVICE</span></div>
          {generation.resume_advice && <TextActionBar text={adviceText} filename={`Hi_Offer_Resume_Advice_${generation.id}.md`} mime="text/markdown;charset=utf-8" />}
        </header>
        {generation.resume_advice ? (
          <div className="advice-list">
            {generation.resume_advice.suggestions.map((item, index) => (
              <section className="advice-item" key={`${item.section}-${item.location}-${index}`}>
                <div className="advice-index">{String(index + 1).padStart(2, "0")}</div>
                <div className="advice-content">
                  <h3>{item.section} · {item.location}</h3>
                  <dl>
                    <div><dt>原内容</dt><dd>{item.original || "原文未提供可直接引用的句子"}</dd></div>
                    <div><dt>问题</dt><dd>{item.problem}</dd></div>
                    <div><dt>修改建议</dt><dd>{item.suggestion}</dd></div>
                    <div><dt>原因</dt><dd>{item.reason}</dd></div>
                  </dl>
                  <span className="priority">优先级 · {priority[item.priority]}</span>
                  {item.action_type && <span className="priority">操作 · {item.action_type}</span>}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <ModuleError message={generation.resume_advice_error || "修改意见尚未生成。"} retry={() => onRetry("resume-advice")} busy={retrying === "resume-advice"} />
        )}
      </article>

      <p className="wish-line">祝大家在平庸的时候不贫困，贫困的时候不平庸</p>
      {!demo && <div className="generation-download"><a className="text-button" href={downloadUrl(`/api/generations/${generation.id}/export/generation`)}>下载完整 Generation</a></div>}
      {generation.debug_enabled && generation.debug_traces && <DebugPanel traces={generation.debug_traces} />}
    </section>
  );
}
