import { useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCheck, UserCheck } from 'lucide-react';
import type {
  ImageryCacheSummary,
  ReviewConfidence,
  ReviewDetermination,
  SiteDetail,
  SiteDetectionsResponse,
  SiteEvidenceResponse,
  SiteReviewHistoryResponse
} from '../types/api';
import { fetchSiteReviews, submitSiteReview } from '../services/api';

interface AnalystReviewPanelProps {
  site: SiteDetail;
  evidence: SiteEvidenceResponse | null;
  imagery: ImageryCacheSummary[];
  detections: SiteDetectionsResponse | null;
  history: SiteReviewHistoryResponse | null;
  onHistoryChange: (history: SiteReviewHistoryResponse) => void;
}

const REASONS = [
  ['AFFIRMATIVE_INDUSTRIAL_EVIDENCE', 'Affirmative industrial evidence'],
  ['AFFIRMATIVE_NONINDUSTRIAL_EVIDENCE', 'Affirmative non-industrial evidence'],
  ['SATELLITE_VISUAL_CORROBORATION', 'Satellite visual corroboration'],
  ['THERMAL_PATTERN_CORROBORATION', 'Thermal-pattern corroboration'],
  ['INSUFFICIENT_OR_CONFLICTING_EVIDENCE', 'Evidence remains insufficient/conflicting']
] as const;

export function AnalystReviewPanel({
  site,
  evidence,
  imagery,
  detections,
  history,
  onHistoryChange
}: AnalystReviewPanelProps) {
  const [reviewer, setReviewer] = useState('analyst_operator');
  const [determination, setDetermination] = useState<ReviewDetermination | null>(null);
  const [confidence, setConfidence] = useState<ReviewConfidence>('MEDIUM');
  const [reasonCodes, setReasonCodes] = useState<string[]>([]);
  const [evidenceChecks, setEvidenceChecks] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const evidenceOptions = [
    {
      id: 'FACILITY_EVIDENCE',
      label: `Facility/reference evidence (${evidence?.total_evidence_count ?? 0})`,
      available: Boolean(evidence?.total_evidence_count),
      refs: [
        ...(evidence?.evidence ?? []).map((item) => `FACILITY:${item.source_name}:${item.evidence_id}`),
        ...(evidence?.event_evidence ?? []).map((item) => `EVENT:${item.source_name}:${item.evidence_id}`)
      ]
    },
    {
      id: 'HLS_PRITHVI_EVIDENCE',
      label: `HLS / Prithvi evidence (${imagery.length})`,
      available: imagery.length > 0,
      refs: imagery.map((item) => `IMAGERY:${item.cache_id}`)
    },
    {
      id: 'FIRMS_SITE_HISTORY',
      label: `Raw FIRMS detections (${detections?.count ?? 0})`,
      available: Boolean(detections?.count),
      refs: [`FIRMS_SITE_HISTORY:${site.site_id}:${detections?.count ?? 0}`]
    },
    {
      id: 'MODEL_TIMELINE',
      label: 'Model B/C temporal record',
      available: Boolean(site.model_b || site.model_c),
      refs: [`MODEL_TIMELINE:${site.site_id}`]
    }
  ];

  const evidenceRefs = evidenceOptions
    .filter((option) => evidenceChecks.includes(option.id))
    .flatMap((option) => option.refs);

  const refreshHistory = async () => {
    onHistoryChange(await fetchSiteReviews(site.site_id));
  };

  const submitState = async (reviewStatus: 'IN_REVIEW' | 'ESCALATED' | 'COMPLETED') => {
    setSubmitting(true);
    setError(null);
    try {
      await submitSiteReview(site.site_id, {
        reviewed_by: reviewer,
        review_status: reviewStatus,
        ...(reviewStatus === 'COMPLETED' && determination
          ? { determination, confidence }
          : {}),
        reason_codes: reviewStatus === 'COMPLETED' ? reasonCodes : [],
        notes: notes || undefined,
        evidence_refs: reviewStatus === 'COMPLETED' ? evidenceRefs : [],
        alert_id: site.active_alert?.alert_id,
        country: 'INDIA'
      });
      await refreshHistory();
      if (reviewStatus === 'COMPLETED') {
        setDetermination(null);
        setReasonCodes([]);
        setEvidenceChecks([]);
        setNotes('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const requiredReason = determination === 'INDUSTRIAL'
    ? 'AFFIRMATIVE_INDUSTRIAL_EVIDENCE'
    : determination === 'NONINDUSTRIAL'
      ? 'AFFIRMATIVE_NONINDUSTRIAL_EVIDENCE'
      : determination === 'REMAIN_UNKNOWN'
        ? 'INSUFFICIENT_OR_CONFLICTING_EVIDENCE'
        : null;
  const canComplete = Boolean(
    reviewer.trim()
    && determination
    && confidence
    && requiredReason
    && reasonCodes.includes(requiredReason)
    && evidenceRefs.length
  );
  const latest = history?.reviews[0];

  return (
    <div className="space-y-3 font-mono">
      <div className="rounded-xl border border-violet-400/30 bg-violet-950/20 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-[11px] font-bold tracking-wider text-violet-200">
            <ClipboardCheck className="h-4 w-4" /> ANALYST ADJUDICATION
          </div>
          <span className="rounded-full border border-violet-400/30 bg-violet-500/10 px-2 py-0.5 text-[9px] text-violet-200">
            {history?.queue_status ?? 'PENDING'}
          </span>
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-400">
          The human determination is stored separately. It never overwrites the frozen Model A result of UNKNOWN.
        </p>
      </div>

      {latest?.consensus_status === 'CONFLICT' && (
        <div className="flex gap-2 rounded-lg border border-rose-500/40 bg-rose-950/25 p-2.5 text-[10px] text-rose-200">
          <AlertTriangle className="h-4 w-4 shrink-0" /> Independent reviewers disagree. Escalation is required; this site is excluded from training.
        </div>
      )}
      {latest?.training_eligible && (
        <div className="flex gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/25 p-2.5 text-[10px] text-emerald-200">
          <CheckCircle2 className="h-4 w-4 shrink-0" /> Two-reviewer consensus verified. This snapshot is eligible for a future curated training export.
        </div>
      )}

      <div className="rounded-xl border border-sky-500/20 bg-[#08101d]/90 p-3 space-y-3">
        <label className="block text-[9px] tracking-wider text-slate-400">
          OPERATOR / BADGE ID
          <input
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
            maxLength={128}
            className="mt-1.5 w-full rounded-md border border-sky-500/25 bg-[#040a13] px-2.5 py-2 text-[11px] text-slate-100 outline-none focus:border-cyan-400/60"
          />
        </label>

        <div>
          <div className="mb-1.5 text-[9px] tracking-wider text-slate-400">DETERMINATION</div>
          <div className="grid grid-cols-3 gap-1.5">
            {([
              ['INDUSTRIAL', 'Industrial'],
              ['NONINDUSTRIAL', 'Non-industrial'],
              ['REMAIN_UNKNOWN', 'Keep unknown']
            ] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setDetermination(value)}
                className={`rounded-md border px-1.5 py-2 text-[9px] transition-colors cursor-pointer ${
                  determination === value
                    ? 'border-violet-400/70 bg-violet-500/20 text-violet-100'
                    : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-sky-400/40'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label className="block text-[9px] tracking-wider text-slate-400">
          CONFIDENCE
          <select
            value={confidence}
            onChange={(event) => setConfidence(event.target.value as ReviewConfidence)}
            className="mt-1.5 w-full rounded-md border border-sky-500/25 bg-[#040a13] px-2.5 py-2 text-[11px] text-slate-100 outline-none"
          >
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </label>

        <div>
          <div className="mb-1.5 text-[9px] tracking-wider text-slate-400">REASON CODES</div>
          <div className="space-y-1.5">
            {REASONS.map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 text-[10px] text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={reasonCodes.includes(value)}
                  onChange={() => setReasonCodes((current) => current.includes(value)
                    ? current.filter((item) => item !== value)
                    : [...current, value])}
                />
                {label}
              </label>
            ))}
          </div>
          {requiredReason && !reasonCodes.includes(requiredReason) && (
            <div className="mt-2 text-[8.5px] text-amber-300/80">
              This determination requires: {requiredReason.replaceAll('_', ' ')}.
            </div>
          )}
        </div>

        <div>
          <div className="mb-1.5 text-[9px] tracking-wider text-slate-400">EVIDENCE REVIEWED</div>
          <div className="space-y-1.5">
            {evidenceOptions.map((option) => (
              <label key={option.id} className={`flex items-center gap-2 text-[10px] ${option.available ? 'text-slate-300 cursor-pointer' : 'text-slate-600'}`}>
                <input
                  type="checkbox"
                  disabled={!option.available}
                  checked={evidenceChecks.includes(option.id)}
                  onChange={() => setEvidenceChecks((current) => current.includes(option.id)
                    ? current.filter((item) => item !== option.id)
                    : [...current, option.id])}
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>

        <label className="block text-[9px] tracking-wider text-slate-400">
          REVIEW NOTES
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            maxLength={4000}
            rows={3}
            className="mt-1.5 w-full resize-none rounded-md border border-sky-500/25 bg-[#040a13] px-2.5 py-2 text-[10px] leading-relaxed text-slate-100 outline-none focus:border-cyan-400/60"
            placeholder="Record the affirmative evidence and remaining uncertainty."
          />
        </label>

        {error && <div className="text-[9px] leading-relaxed text-rose-300">{error}</div>}

        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting || !reviewer.trim()}
            onClick={() => void submitState('IN_REVIEW')}
            className="flex-1 rounded-md border border-sky-400/30 bg-sky-950/30 px-2 py-2 text-[9px] text-sky-200 disabled:opacity-40 cursor-pointer"
          >
            MARK IN REVIEW
          </button>
          <button
            type="button"
            disabled={submitting || !canComplete}
            onClick={() => void submitState('COMPLETED')}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-emerald-400/40 bg-emerald-950/30 px-2 py-2 text-[9px] text-emerald-200 disabled:opacity-40 cursor-pointer"
          >
            <UserCheck className="h-3.5 w-3.5" /> SUBMIT REVIEW
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-[9px] tracking-wider text-slate-500">APPEND-ONLY REVIEW HISTORY</div>
        {(history?.reviews ?? []).length === 0 ? (
          <div className="rounded-lg border border-white/10 p-3 text-[10px] text-slate-500">No analyst review events recorded.</div>
        ) : history?.reviews.map((review) => (
          <div key={review.review_id} className="rounded-lg border border-white/10 bg-white/[0.025] p-2.5 text-[9px]">
            <div className="flex justify-between gap-2 text-slate-300">
              <b>{review.determination ?? review.review_status}</b>
              <span className="text-slate-500">{review.consensus_status}</span>
            </div>
            <div className="mt-1 text-slate-500">{review.reviewed_by} · {new Date(review.reviewed_at).toLocaleString()}</div>
            {review.notes && <div className="mt-1.5 leading-relaxed text-slate-400">{review.notes}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
