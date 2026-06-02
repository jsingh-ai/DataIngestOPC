import { Link, Outlet, useNavigate } from "react-router-dom";
import { setToken } from "../api/client";

export function Layout(): JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-kicker">Industrial Data</div>
          <h1>OPC Platform</h1>
        </div>
        <nav className="nav-list">
          <Link to="/machines">Machines</Link>
          <Link to="/health">Health</Link>
          <Link to="/collector">Collector</Link>
        </nav>
        <button
          className="ghost-button"
          onClick={() => {
            setToken(null);
            navigate("/login");
          }}
        >
          Logout
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
