import React from 'react';

export default function PlaceholderPanel({ icon = '▣', title, description, message }) {
    return (
        <section className="panel placeholder-panel">
            <div className="panel-title"><span className="title-icon">{icon}</span><div><h2>{title}</h2><p>{description}</p></div></div>
            <p>{message}</p>
        </section>
    );
}