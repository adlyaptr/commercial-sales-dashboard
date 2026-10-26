import React from 'react';

const iconPaths = {
    volume: (
        <>
            <path d="M4 19V9m5 10V5m5 14v-7m5 7V3" />
            <path d="M2 21h20" />
        </>
    ),
    price: (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="M15.5 8.5c-.7-.7-1.7-1-3-1-1.7 0-2.8.8-2.8 2s1.1 1.8 2.8 2.2 2.8 1 2.8 2.2-1.1 2-2.8 2c-1.3 0-2.3-.4-3-1.1M12.5 5.5v13" />
        </>
    ),
    complaint: (
        <>
            <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-3 2v-5.5A7.5 7.5 0 1 1 20 11.5Z" />
            <path d="M8 11.5h.01M12 11.5h.01M16 11.5h.01" />
        </>
    ),
    sales: (
        <>
            <path d="M4 19V5m0 14h16" />
            <path d="m7 15 4-4 3 2 5-6" />
            <path d="M15 7h4v4" />
        </>
    ),
    region: (
        <>
            <path d="M12 21s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z" />
            <circle cx="12" cy="9" r="2.2" />
        </>
    ),
    customer: (
        <>
            <circle cx="9" cy="8" r="3" />
            <path d="M3.5 20v-1.5a5.5 5.5 0 0 1 11 0V20M16 5.5a3 3 0 0 1 0 5.8m1.5 3a4.5 4.5 0 0 1 3 4.2V20" />
        </>
    ),
    filter: (
        <>
            <path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z" />
        </>
    ),
    calendar: (
        <>
            <rect x="3.5" y="5" width="17" height="16" rx="2" />
            <path d="M8 3v4m8-4v4M3.5 10h17m-11 4h.01m4 0h.01m4 0h.01M9 17h.01m4 0h.01" />
        </>
    ),
};

export default function SectionIcon({ name }) {
    return (
        <span className="section-icon" aria-hidden="true">
            <svg
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
            >
                {iconPaths[name]}
            </svg>
        </span>
    );
}
