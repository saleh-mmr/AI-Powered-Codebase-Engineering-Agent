import { SystemStatus } from '../features/system/SystemStatus';

export function App() {
  return (
    <div className="workspace">
      <header>
        <a className="brand" href="/" aria-label="RepoPilot AI home">
          <span className="brand-mark" aria-hidden="true">
            rp
          </span>
          RepoPilot <span className="brand-ai">AI</span>
        </a>
        <span className="milestone">01 / Foundation</span>
      </header>
      <main>
        <div className="intro">
          <span className="eyebrow">CODEBASE INTELLIGENCE</span>
          <h1>
            Understand the code.
            <br />
            <span>Build with confidence.</span>
          </h1>
          <p>
            A workspace for grounded repository exploration. We’re starting with
            a dependable foundation for everything that comes next.
          </p>
        </div>
        <div className="grid">
          <SystemStatus />
          <section className="next-card" aria-labelledby="next-title">
            <span className="eyebrow">THE ROAD AHEAD</span>
            <h2 id="next-title">From source to understanding.</h2>
            <ol>
              <li>
                <span>01</span>
                <div>
                  <strong>Foundation</strong>
                  <p>Application, API, and database readiness.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Your workspace</strong>
                  <p>Secure sign-in and repository ownership.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Repository exploration</strong>
                  <p>Import, index, and ask questions with sources.</p>
                </div>
              </li>
            </ol>
            <p className="note">
              Repository import and AI chat arrive in later milestones.
            </p>
          </section>
        </div>
      </main>
      <footer>
        RepoPilot AI <span>Milestone 1 · React / FastAPI / PostgreSQL</span>
      </footer>
    </div>
  );
}
