import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import Home from './pages/Home';
import SkillPage from './pages/SkillPage';

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/skill/:name" element={<SkillPage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
