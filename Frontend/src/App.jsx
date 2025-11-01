import React,{useState} from "react";
import "./App.css";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ClientDetail from "./components/ClientDetail/ClientDetail";
import ClientsOverview from "./components/ClientsOverview"
import Dashboard from "./components/Dashboard";
import AgentsPage from "./components/AgentsPage"
import ShellBar from "./components/ShellBar";
import ChatbotWidget from "./components/ChatbotWidget";

function App() {
  const [chatOpen, setChatOpen] = useState(false);

  const toggleChat = () => setChatOpen(!chatOpen);
  return (
    <Router>
      <ShellBar onChatToggle={toggleChat} />
      <Routes>
      <Route path="/" element={<Dashboard />} />
        <Route path="/client-detail" element={<ClientDetail />} />
        <Route path="/clients" element={<ClientsOverview />} />
        <Route path="/agents" element = {<AgentsPage/>}/>
      </Routes>
      <ChatbotWidget isOpen={chatOpen} onToggle={toggleChat} />
    </Router>
  );
}

export default App;
