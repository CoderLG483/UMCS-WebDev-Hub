import React, { useState } from 'react';
import './HomePage.css';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState('all');

  const pillars = [
    {
      id: 'web',
      tag: 'Web Dev',
      title: 'The Core Ecosystem',
      desc: 'Building responsive portals, APIs, and modern platforms for society members.',
      icon: '🌐',
    },
    {
      id: 'games',
      tag: 'Game Dev',
      title: 'The Arcade & Logic Zone',
      desc: 'Interactive 2D challenges, logic puzzles, and weekly club competitions.',
      icon: '🎮',
    },
    {
      id: 'ai',
      tag: 'Artificial Intelligence',
      title: 'Smart Hub & Copilots',
      desc: 'AI learning assistants, automated project recommendations, and smart search.',
      icon: '🤖',
    },
    {
      id: 'data',
      tag: 'Data Science',
      title: 'Telemetry & Analytics',
      desc: 'Member skill heatmaps, engagement analytics, and predictive club trends.',
      icon: '📊',
    },
  ];

  const featuredProjects = [
    {
      title: 'Campus Rush',
      category: 'Game Dev',
      author: 'Student Showcase',
      desc: 'Campus navigation and obstacle runner game.',
      stars: 42,
    },
    {
      title: 'StudyBuddy AI',
      category: 'AI / ML',
      author: 'AI Stream',
      desc: 'RAG-powered exam prep assistant for CS coursework.',
      stars: 58,
    },
    {
      title: 'StackTracker',
      category: 'Data Science',
      author: 'Analytics Team',
      desc: 'Live dashboard analyzing tech stack adoption across campus.',
      stars: 31,
    },
  ];

  const filteredPillars = activeTab === 'all' 
    ? pillars 
    : pillars.filter(p => p.id === activeTab);

  return (
    <div className="homepage-container">
      {/* Navigation */}
      <header className="navbar">
        <div className="brand">
          <span className="brand-badge">DevSphere</span>
          <span className="brand-sub">Innovation Hub</span>
        </div>
        <nav className="nav-links">
          <a href="#pillars">Pillars</a>
          <a href="#showcase">Showcase</a>
          <a href="#stats">Stats</a>
          <button className="btn-secondary">Log In</button>
          <button className="btn-primary">Join DevSphere</button>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">Tagline: Learn. Build. Play. Collaborate.</div>
        <h1 className="hero-title">
          The Central Engine for <br />
          <span className="highlight-text">Computing Innovation</span>
        </h1>
        <p className="hero-subtitle">
          DevSphere unites Web Development, Game Engineering, Artificial Intelligence, 
          and Data Science into one collaborative ecosystem.
        </p>
        <div className="hero-actions">
          <button className="btn-primary">Explore Platform</button>
          <button className="btn-outline">Browse Source Code</button>
        </div>
      </section>

      {/* Pillars Section */}
      <section id="pillars" className="section-container">
        <div className="section-header">
          <h2>Specialized Innovation Streams</h2>
          <p>Explore the four integrated divisions that power the hub.</p>
        </div>

        {/* Tab Filters */}
        <div className="filter-bar">
          <button 
            className={`filter-btn ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            All Streams
          </button>
          <button 
            className={`filter-btn ${activeTab === 'web' ? 'active' : ''}`}
            onClick={() => setActiveTab('web')}
          >
            Web Dev
          </button>
          <button 
            className={`filter-btn ${activeTab === 'games' ? 'active' : ''}`}
            onClick={() => setActiveTab('games')}
          >
            Game Dev
          </button>
          <button 
            className={`filter-btn ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            AI
          </button>
          <button 
            className={`filter-btn ${activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('data')}
          >
            Data Science
          </button>
        </div>

        <div className="grid-cards">
          {filteredPillars.map((pillar) => (
            <div key={pillar.id} className="pillar-card">
              <div className="card-icon">{pillar.icon}</div>
              <span className="card-tag">{pillar.tag}</span>
              <h3>{pillar.title}</h3>
              <p>{pillar.desc}</p>
              <a href={`/${pillar.id}`} className="card-link">View division &rarr;</a>
            </div>
          ))}
        </div>
      </section>

      {/* Featured Showcase */}
      <section id="showcase" className="section-container">
        <div className="section-header">
          <h2>Featured Member Creations</h2>
          <p>Recent projects shipped by student builders across disciplines.</p>
        </div>

        <div className="grid-cards three-col">
          {featuredProjects.map((item, index) => (
            <div key={index} className="showcase-card">
              <div className="showcase-meta">
                <span className="badge">{item.category}</span>
                <span className="stars">★ {item.stars}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
              <div className="showcase-footer">
                <span>By {item.author}</span>
                <button className="btn-sm">Inspect</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Metric Counters */}
      <section id="stats" className="stats-section">
        <div className="stat-box">
          <h3>4</h3>
          <p>Core Streams</p>
        </div>
        <div className="stat-box">
          <h3>3</h3>
          <p>Skill Tiers</p>
        </div>
        <div className="stat-box">
          <h3>100%</h3>
          <p>Student-Built</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <p>© 2026 DevSphere. Built with React by the Computing Society Web Division.</p>
      </footer>
    </div>
  );
}