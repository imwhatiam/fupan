import React from 'react';

const RISE_COLOR = '#cf1322';
const FALL_COLOR = '#389e0d';

function StockChip({ stock }) {
  const color = stock.pctChg >= 0 ? RISE_COLOR : FALL_COLOR;
  return (
    <span style={{
      display: 'inline-block',
      margin: '3px 4px',
      padding: '4px 8px',
      borderRadius: 4,
      border: `1px solid ${color}`,
      color,
      fontSize: 12,
      whiteSpace: 'nowrap',
    }}>
      {stock.name}（{stock.pctChg > 0 ? '+' : ''}{stock.pctChg}%，{stock.amount}亿）
    </span>
  );
}

function StockCell({ stocks }) {
  if (!stocks || stocks.length === 0)
    return <span style={{ color: '#999', fontSize: 12 }}>无</span>;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
      {stocks.map((s, i) => <StockChip key={i} stock={s} />)}
    </div>
  );
}

export default function StockTable({ date, data }) {
  if (!data) return null;
  const { sse, szse } = data;

  const th = {
    padding: '8px 12px',
    background: '#fafafa',
    borderBottom: '1px solid #e8e8e8',
    fontWeight: 600,
    textAlign: 'center',
    whiteSpace: 'nowrap',
  };
  const td = {
    padding: '10px 12px',
    borderBottom: '1px solid #f0f0f0',
    verticalAlign: 'top',
  };
  const label = { ...td, textAlign: 'center', fontWeight: 600, width: 60, color: '#555' };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,.08)' }}>
        <thead>
          <tr>
            <th style={th}>{date}</th>
            <th style={{ ...th, color: RISE_COLOR }}>涨幅超8% 成交超8亿</th>
            <th style={{ ...th, color: FALL_COLOR }}>跌幅超8% 成交超8亿</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={label}>上证</td>
            <td style={td}><StockCell stocks={sse.rise} /></td>
            <td style={td}><StockCell stocks={sse.fall} /></td>
          </tr>
          <tr>
            <td style={label}>深证</td>
            <td style={td}><StockCell stocks={szse.rise} /></td>
            <td style={td}><StockCell stocks={szse.fall} /></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
