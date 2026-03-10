import React, { useState } from 'react';

function IndustryRow({ item }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr
        onClick={() => setOpen(o => !o)}
        style={{ cursor: 'pointer', transition: 'background 0.15s' }}
        onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
        onMouseLeave={e => e.currentTarget.style.background = ''}
      >
        <td style={tdS}>{item.industry}</td>
        <td style={{ ...tdS, textAlign: 'center' }}>{item.stock_count}</td>
        <td style={{ ...tdS, textAlign: 'center', color: '#cf1322' }}>
          {item.avg_pctChg > 0 ? '+' : ''}{item.avg_pctChg.toFixed(2)}%
        </td>
        <td style={{ ...tdS, textAlign: 'center' }}>
          {(item.industry_amount_ratio * 100).toFixed(3)}%
        </td>
        <td style={{ ...tdS, textAlign: 'center', color: '#1677ff' }}>
          {item.score.toFixed(4)}
        </td>
        <td style={{ ...tdS, textAlign: 'center', color: '#999', fontSize: 12 }}>
          {open ? '▲ 收起' : '▼ 展开'}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} style={{ padding: '8px 16px', background: '#f9f9f9', borderBottom: '1px solid #f0f0f0' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(item.stocks || []).map((s, i) => (
                <span key={i} style={{
                  padding: '3px 8px', borderRadius: 4,
                  background: '#fff7e6', border: '1px solid #ffc069',
                  fontSize: 12, color: '#d46b08'
                }}>
                  {s.name} {s.pctChg > 0 ? '+' : ''}{s.pctChg}% {s.amount}亿
                </span>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

const thS = { padding: '8px 12px', background: '#fafafa', borderBottom: '1px solid #e8e8e8', fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap' };
const tdS = { padding: '9px 12px', borderBottom: '1px solid #f0f0f0', fontSize: 13 };

export default function IndustryChart({ title, summary, chartB64 }) {
  const [showChart, setShowChart] = useState(false);
  if (!summary) return null;
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>{title}</h3>
        {chartB64 && (
          <button
            onClick={() => setShowChart(v => !v)}
            style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #d9d9d9', background: '#fff', fontSize: 13, color: '#555' }}
          >
            {showChart ? '隐藏图表' : '查看图表'}
          </button>
        )}
      </div>
      {showChart && chartB64 && (
        <div style={{ marginBottom: 16, textAlign: 'center' }}>
          <img src={`data:image/png;base64,${chartB64}`} alt={title} style={{ maxWidth: '100%', borderRadius: 6 }} />
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,.08)' }}>
          <thead>
            <tr>
              <th style={thS}>行业</th>
              <th style={{ ...thS, textAlign: 'center' }}>股票数</th>
              <th style={{ ...thS, textAlign: 'center' }}>平均涨幅</th>
              <th style={{ ...thS, textAlign: 'center' }}>成交占比</th>
              <th style={{ ...thS, textAlign: 'center' }}>综合评分</th>
              <th style={{ ...thS, textAlign: 'center' }}>明细</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((item, i) => <IndustryRow key={i} item={item} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
