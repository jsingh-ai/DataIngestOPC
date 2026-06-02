import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, setToken } from "../api/client";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123!");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const token = await login(username, password);
      setToken(token);
      navigate("/machines");
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  return (
    <div className="login-page">
      <form className="panel login-panel" onSubmit={handleSubmit}>
        <div className="brand-kicker">OPC UA Collection Admin</div>
        <h1>Login</h1>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <button className="primary-button" type="submit">
          Sign In
        </button>
      </form>
    </div>
  );
}
