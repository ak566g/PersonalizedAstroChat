import { useCallback, useState } from "react";
import { AuthScreen } from "./components/AuthScreen";
import { ChatApp } from "./components/ChatApp";
export const TOKEN_KEY = "astrochat.session";
export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const signIn = useCallback((next: string) => {
    localStorage.setItem(TOKEN_KEY, next);
    setToken(next);
  }, []);
  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);
  return token ? (
    <ChatApp key={token} token={token} onSignOut={signOut} />
  ) : (
    <AuthScreen onAuthenticated={signIn} />
  );
}
