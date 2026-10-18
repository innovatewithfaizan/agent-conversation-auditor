import { HashRouter, NavLink, Route, Routes } from "react-router-dom";
import ConversationDetail from "./pages/ConversationDetail";
import ConversationList from "./pages/ConversationList";
import LiveAudit from "./pages/LiveAudit";
import Overview from "./pages/Overview";
import PolicyPage from "./pages/PolicyPage";

const REPO = "https://github.com/innovatewithfaizan/agent-conversation-auditor";

export default function App() {
  return (
    // Hash routing keeps deep links working on static hosts such as GitHub Pages.
    <HashRouter>
      <nav className="nav">
        <div className="nav-inner">
          <NavLink to="/" className="nav-brand">Conversation Auditor</NavLink>
          <div className="nav-links">
            <NavLink to="/" end>Overview</NavLink>
            <NavLink to="/conversations">Conversations</NavLink>
            <NavLink to="/audit">Live audit</NavLink>
            <NavLink to="/policy">Policy</NavLink>
            <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          </div>
        </div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/conversations" element={<ConversationList />} />
          <Route path="/conversations/:id" element={<ConversationDetail />} />
          <Route path="/audit" element={<LiveAudit />} />
          <Route path="/policy" element={<PolicyPage />} />
        </Routes>
        <footer>
          Conversations from the ABCD dataset (ASAPP, MIT licence) with planted test violations; fake personal details
          from Faker. Not legal advice. <a href={REPO}>Source code</a>.
        </footer>
      </main>
    </HashRouter>
  );
}
