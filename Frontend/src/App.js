import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import BursaryList from "./pages/BursaryList";
import BursaryDetail from "./pages/BursaryDetail";
import Chat from "./pages/Chat";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/search" element={<BursaryList />} />
        <Route path="/bursaries/:id" element={<BursaryDetail />} />
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </BrowserRouter>
  );
}
