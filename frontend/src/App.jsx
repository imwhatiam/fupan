/**
 * App.jsx
 *
 * Root application component for the Daily Market Review (每日复盘) system.
 *
 * Layout:
 *   Header → Control bar (date picker) → Hint banner → Stat cards → Tabs → Tab content
 *
 * Tabs:
 *   1. 复盘主表   – Fupan: stocks with large moves and high volume
 *   2. 行业分析   – Industry: sector analysis with charts
 *   3. 百日新高   – Hundred Day: 100-day new high / new low analysis
 */
import React, { useState, useEffect } from 'react';
import { api } from './services/api.js';
import StockTable from './components/StockTable.jsx';
import IndustryChart from './components/IndustryChart.jsx';
import HundredDayView from './components/HundredDayView.jsx';

// ─── Tab identifier constants ─────────────────────────────────────────────────
const TAB = { FUPAN: 'fupan', INDUSTRY: 'industry', HUNDRED: 'hundred' };

// ─── Date picker with confirm button ─────────────────────────────────────────
/**
 * DatePicker renders an <input type="date"> with a confirm button.
 * The parent is only notified via `onChange` when the user clicks "Confirm",
 * preventing unnecessary re-fetches on every keystroke.
 *
 * @param {{ value: string, onChange: (date: string) => void }} props
 */
function DatePicker({ value, onChange }) {
  const [input, setInput] = useState(value || '');

  // Keep local state in sync when the parent updates `value`
  useEffect(() => { setInput(value || ''); }, [value]);

  const confirm = () => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(input)) onChange(input);
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <input
        type="date"
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && confirm()}
        style={{
          padding: '5px 10px', borderRadius: 6,
          border: '1px solid #d9d9d9', fontSize: 14,
          background: '#fff', cursor: 'pointer',
        }}
      />
      <button
        onClick={confirm}
        style={{
          padding: '5px 16px', borderRadius: 6, border: 'none',
          background: '#1677ff', color: '#fff', fontSize: 14,
          fontWeight: 500, cursor: 'pointer',
        }}
      >
        确定
      </button>
    </div>
  );
}

// ─── Summary stat card ────────────────────────────────────────────────────────
/**
 * @param {{ label: string, value: any, color?: string }} props
 */
function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 8, padding: '12px 20px',
      boxShadow: '0 1px 4px rgba(0,0,0,.08)', minWidth: 100, textAlign: 'center',
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || '#333' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{label}</div>
    </div>
  );
}

// ─── All-codes copy panel ─────────────────────────────────────────────────────
/**
 * Renders the full list of involved stock codes with a one-click copy button.
 * Matches the original notebook's `','.join(all_codes)` output.
 *
 * @param {{ codes: string[] }} props
 */
function AllCodesPanel({ codes }) {
  const [copied, setCopied] = useState(false);
  if (!codes || codes.length === 0) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(codes.join(',')).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div style={{
      marginTop: 20, background: '#fff', borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,.08)', padding: '16px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>
          涉及股票代码（{codes.length} 只）
        </span>
        <button
          onClick={handleCopy}
          style={{
            padding: '4px 14px', borderRadius: 5, cursor: 'pointer',
            border: '1px solid #d9d9d9',
            background: copied ? '#f6ffed' : '#fff',
            color: copied ? '#389e0d' : '#555', fontSize: 13,
          }}
        >{copied ? '✓ 已复制' : '复制全部'}</button>
      </div>
      <div style={{
        fontFamily: 'monospace', fontSize: 13, color: '#555',
        background: '#f5f5f5', borderRadius: 6, padding: '10px 14px',
        lineHeight: 1.9, wordBreak: 'break-all',
      }}>
        {codes.map((code, i) => (
          <span key={code}>
            <span style={{ color: '#1677ff' }}>{code}</span>
            {i < codes.length - 1 && <span style={{ color: '#bbb' }}>,</span>}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Root component ───────────────────────────────────────────────────────────
export default function App() {
  // Active tab identifier
  const [activeTab,      setActiveTab]     = useState(TAB.FUPAN);

  // Currently selected date string ("YYYY-MM-DD")
  const [selectedDate,   setSelectedDate]  = useState('');

  // Hint message shown to the user (e.g. "Data updates at 18:00 on trading days")
  const [hint,           setHint]          = useState('');

  // Per-tab data payloads
  const [fupanData,      setFupanData]     = useState(null);
  const [industryData,   setIndustryData]  = useState(null);
  const [hundredData,    setHundredData]   = useState(null);

  // Loading / error states
  const [loading,        setLoading]       = useState(false);
  const [initing,        setIniting]       = useState(true);
  const [error,          setError]         = useState('');

  // ── Page init: call POST /api/init/ to resolve the starting date ────────────
  useEffect(() => {
    api.init()
      .then(res => {
        setHint(res.hint || '');
        if (res.date) setSelectedDate(res.date);
      })
      .catch(() => setHint('服务不可用，请检查后端是否已启动。'))
      .finally(() => setIniting(false));
  }, []);

  // ── Re-fetch data whenever the selected date or active tab changes ──────────
  useEffect(() => {
    if (!selectedDate || initing) return;

    setError('');
    setLoading(true);

    let request;
    if (activeTab === TAB.FUPAN) {
      request = api.getFupan(selectedDate).then(d => { setFupanData(d); setHint(''); });
    } else if (activeTab === TAB.INDUSTRY) {
      request = api.getIndustry(selectedDate).then(d => { setIndustryData(d); setHint(''); });
    } else {
      request = api.getHundredDay(selectedDate).then(d => { setHundredData(d); setHint(''); });
    }

    request
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedDate, activeTab, initing]);

  // ── Tab button renderer ─────────────────────────────────────────────────────
  const tabBtn = (id, label) => (
    <button
      key={id}
      onClick={() => setActiveTab(id)}
      style={{
        padding: '8px 20px', border: 'none', borderRadius: '6px 6px 0 0',
        background: activeTab === id ? '#1677ff' : '#e6e6e6',
        color: activeTab === id ? '#fff' : '#555',
        fontWeight: activeTab === id ? 600 : 400,
        fontSize: 14, marginRight: 4, cursor: 'pointer',
      }}
    >{label}</button>
  );

  return (
    <div style={{ minHeight: '100vh', paddingBottom: 40 }}>

      {/* ── Top header bar ─────────────────────────────────────────────────── */}
      <div style={{
        background: '#1677ff', padding: '0 24px',
        display: 'flex', alignItems: 'center', height: 56,
      }}>
        <span style={{ color: '#fff', fontSize: 20, fontWeight: 700, letterSpacing: 1 }}>
          📈 每日复盘系统
        </span>
      </div>

      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 24px 0' }}>

        {/* ── Date picker control bar ─────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 14, color: '#555' }}>选择日期：</span>
          <DatePicker
            value={selectedDate}
            onChange={date => {
              setSelectedDate(date);
              // Clear stale data so the loading indicator shows correctly
              setFupanData(null);
              setIndustryData(null);
              setHundredData(null);
            }}
          />
        </div>

        {/* ── Hint banner ─────────────────────────────────────────────────── */}
        {hint && (
          <div style={{
            marginBottom: 16, padding: '8px 14px', borderRadius: 6,
            background: '#e6f4ff', border: '1px solid #91caff',
            fontSize: 13, color: '#0958d9',
          }}>
            ℹ️ {hint}
          </div>
        )}

        {/* ── Stat cards (contextual per active tab) ──────────────────────── */}
        {fupanData && activeTab === TAB.FUPAN && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            <StatCard label="上证上涨"    value={fupanData.stats.sse_rise_count}  color="#cf1322" />
            <StatCard label="上证下跌"    value={fupanData.stats.sse_fall_count}  color="#389e0d" />
            <StatCard label="深证上涨"   value={fupanData.stats.szse_rise_count} color="#cf1322" />
            <StatCard label="深证下跌"   value={fupanData.stats.szse_fall_count} color="#389e0d" />
            <StatCard label="涉及股票" value={fupanData.all_codes.length}      color="#1677ff" />
          </div>
        )}
        {industryData && activeTab === TAB.INDUSTRY && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            <StatCard label="全市场成交（亿）" value={industryData.total_amount_yi} color="#1677ff" />
          </div>
        )}
        {hundredData && activeTab === TAB.HUNDRED && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            <StatCard label="股票总数"  value={hundredData.total_stocks} color="#333"     />
            <StatCard label="百日新高"  value={hundredData.high_count}   color="#cf1322"  />
            <StatCard label="百日新低"   value={hundredData.low_count}    color="#389e0d"  />
          </div>
        )}

        {/* ── Tab navigation ──────────────────────────────────────────────── */}
        <div>
          {tabBtn(TAB.FUPAN,    '复盘主表')}
          {tabBtn(TAB.INDUSTRY, '行业分析')}
          {tabBtn(TAB.HUNDRED,  '百日新高')}
        </div>

        {/* ── Tab content panel ───────────────────────────────────────────── */}
        <div style={{
          background: '#fff', borderRadius: '0 8px 8px 8px',
          padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,.08)', minHeight: 300,
        }}>

          {/* Loading state */}
          {(loading || initing) && (
            <div style={{ textAlign: 'center', padding: 60, color: '#999', fontSize: 16 }}>
              {initing ? '初始化中…' : '加载中…'}
            </div>
          )}

          {/* Error state */}
          {!loading && !initing && error && (
            <div style={{
              color: '#cf1322', background: '#fff2f0',
              border: '1px solid #ffccc7', borderRadius: 6, padding: '12px 16px',
            }}>
              ⚠️ {error}
              <div style={{ fontSize: 12, color: '#888', marginTop: 6 }}>
                该日期暂无数据，请选择其他日期。
              </div>
            </div>
          )}

          {/* Tab: 复盘主表 */}
          {!loading && !initing && !error && activeTab === TAB.FUPAN && fupanData && (
            <>
              <StockTable date={selectedDate} data={fupanData} />
              <AllCodesPanel codes={fupanData.all_codes} />
            </>
          )}

          {/* Tab: 行业分析 */}
          {!loading && !initing && !error && activeTab === TAB.INDUSTRY && industryData && (
            <>
              <IndustryChart
                title="涨幅超过5% — 行业分布（Top 10）"
                summary={industryData.above_5pct?.summary}
                chartB64={industryData.above_5pct?.chart_b64}
              />
              <IndustryChart
                title="全市场涨幅 Top 10% — 行业分布（Top 10）"
                summary={industryData.top_10pct?.summary}
                chartB64={industryData.top_10pct?.chart_b64}
              />
            </>
          )}

          {/* Tab: 百日新高 */}
          {!loading && !initing && !error && activeTab === TAB.HUNDRED && hundredData && (
            <HundredDayView data={hundredData} />
          )}

        </div>
      </div>
    </div>
  );
}
