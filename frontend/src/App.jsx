import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import JobStatus from './pages/JobStatus';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/jobs/:id" element={<JobStatus />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
