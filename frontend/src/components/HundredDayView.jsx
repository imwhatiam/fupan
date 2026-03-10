/**
 * HundredDayView.jsx
 *
 * Displays the 100-day new high / new low analysis:
 *   1. A sector table showing which industries have the most stocks hitting
 *      100-day highs (top) or 100-day lows (bottom).
 *   2. A bar chart (server-rendered PNG) showing the ratio of 100-day high/low
 *      stocks relative to the total stock count over recent trading days.
 */
import React, { useState } from 'react';

// ─── Style constants ─────────────────────────────────────────────────────────
const RISE_COLOR  = '#cf1322';  // Red for new highs
const FALL_COLOR  = '#389e0d';  // Green for new lows
const BORDER      = '1px solid #f0f0f0';

const thStyle = {
    padding: '9px 14px',
    background: '#fafafa',
    borderBottom: '1px solid #e8e8e8',
    fontWeight: 600,
    fontSize: 13,
    whiteSpace: 'nowrap',
};

const tdStyle = {
    padding: '9px 14px',
    borderBottom: BORDER,
    fontSize: 13,
    verticalAlign: 'top',
};

// ─── Single sector row (expandable stock chips) ───────────────────────────────
function SectorRow({ item, type }) {
    const [open, setOpen] = useState(false);
    const isHigh   = type === 'high';
    const accent   = isHigh ? RISE_COLOR : FALL_COLOR;
    const prefix   = isHigh ? '+' : '−';

    return (
        <>
            <tr
                onClick={() => setOpen(o => !o)}
                style={{ cursor: 'pointer' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#fafafa')}
                onMouseLeave={e => (e.currentTarget.style.background = '')}
            >
                {/* Sector name */}
                <td style={{ ...tdStyle, color: accent, fontWeight: 600 }}>
                    {prefix} {item.industry}
                </td>

                {/* Stock count */}
                <td style={{ ...tdStyle, textAlign: 'center', color: accent }}>
                    {item.count}
                </td>

                {/* Expand toggle */}
                <td style={{ ...tdStyle, textAlign: 'center', color: '#bbb', fontSize: 11 }}>
                    {open ? '▲' : '▼'}
                </td>
            </tr>

            {/* Expanded: individual stock name chips */}
            {open && (
                <tr>
                    <td
                        colSpan={3}
                        style={{
                            padding: '8px 16px 12px',
                            background: '#f9f9f9',
                            borderBottom: BORDER,
                        }}
                    >
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                            {item.stocks.map((name, i) => (
                                <span
                                    key={i}
                                    style={{
                                        padding: '3px 10px',
                                        borderRadius: 4,
                                        background: isHigh ? '#fff1f0' : '#f6ffed',
                                        border: `1px solid ${accent}`,
                                        color: accent,
                                        fontSize: 12,
                                    }}
                                >
                                    {name}
                                </span>
                            ))}
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
}

// ─── Sector table (shared for high / low) ────────────────────────────────────
function SectorTable({ title, rows, type }) {
    if (!rows || rows.length === 0) {
        return (
            <div style={{ color: '#999', fontSize: 13, padding: '12px 0' }}>
                {title}: no data
            </div>
        );
    }

    return (
        <div style={{ marginBottom: 24 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: '#333' }}>
                {title}
            </h4>
            <div style={{ overflowX: 'auto' }}>
                <table
                    style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        background: '#fff',
                        borderRadius: 8,
                        overflow: 'hidden',
                        boxShadow: '0 1px 4px rgba(0,0,0,.07)',
                    }}
                >
                    <thead>
                        <tr>
                            <th style={thStyle}>Sector / Industry</th>
                            <th style={{ ...thStyle, textAlign: 'center' }}>Count</th>
                            <th style={{ ...thStyle, textAlign: 'center', width: 50 }}>Detail</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((item, i) => (
                            <SectorRow key={i} item={item} type={type} />
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// ─── Summary stat badge ───────────────────────────────────────────────────────
function Badge({ label, value, color }) {
    return (
        <div
            style={{
                display: 'inline-flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '10px 20px',
                background: '#fff',
                borderRadius: 8,
                boxShadow: '0 1px 4px rgba(0,0,0,.07)',
                minWidth: 90,
            }}
        >
            <span style={{ fontSize: 22, fontWeight: 700, color }}>{value}</span>
            <span style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{label}</span>
        </div>
    );
}

// ─── Main export ──────────────────────────────────────────────────────────────
export default function HundredDayView({ data }) {
    const [showChart, setShowChart] = useState(true);

    if (!data) return null;

    const {
        new_high_sectors,
        new_low_sectors,
        ratio_chart_b64,
        total_stocks,
        high_count,
        low_count,
    } = data;

    return (
        <div>
            {/* Summary badges */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                <Badge label="Total Stocks"    value={total_stocks} color="#333"       />
                <Badge label="100-Day High"    value={high_count}   color={RISE_COLOR} />
                <Badge label="100-Day Low"     value={low_count}    color={FALL_COLOR} />
                <Badge
                    label="High Ratio"
                    value={total_stocks > 0 ? `${(high_count / total_stocks * 100).toFixed(1)}%` : '—'}
                    color={RISE_COLOR}
                />
                <Badge
                    label="Low Ratio"
                    value={total_stocks > 0 ? `${(low_count / total_stocks * 100).toFixed(1)}%` : '—'}
                    color={FALL_COLOR}
                />
            </div>

            {/* Ratio chart (toggle) */}
            {ratio_chart_b64 && (
                <div style={{ marginBottom: 28 }}>
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: 10,
                        }}
                    >
                        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>
                            100-Day High / Low Ratio Chart
                        </h3>
                        <button
                            onClick={() => setShowChart(v => !v)}
                            style={{
                                padding: '4px 12px',
                                borderRadius: 5,
                                border: '1px solid #d9d9d9',
                                background: '#fff',
                                fontSize: 13,
                                cursor: 'pointer',
                                color: '#555',
                            }}
                        >
                            {showChart ? 'Hide Chart' : 'Show Chart'}
                        </button>
                    </div>
                    {showChart && (
                        <img
                            src={`data:image/png;base64,${ratio_chart_b64}`}
                            alt="100-day high/low ratio chart"
                            style={{
                                maxWidth: '100%',
                                borderRadius: 8,
                                boxShadow: '0 1px 6px rgba(0,0,0,.1)',
                            }}
                        />
                    )}
                </div>
            )}

            {/* Two-column sector tables */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                    gap: 24,
                }}
            >
                <SectorTable
                    title="100-Day New High — Top Sectors"
                    rows={new_high_sectors}
                    type="high"
                />
                <SectorTable
                    title="100-Day New Low — Top Sectors"
                    rows={new_low_sectors}
                    type="low"
                />
            </div>
        </div>
    );
}
