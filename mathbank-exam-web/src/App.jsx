import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Signup from "./pages/Signup.jsx";
import Login from "./pages/Login.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import RequestPaper from "./pages/RequestPaper.jsx";
import GeneratingPaper from "./pages/GeneratingPaper.jsx";
import TakeExam from "./pages/TakeExam.jsx";
import Review from "./pages/Review.jsx";
import { isLoggedIn } from "./api.js";

function RequireAuth({ children }) {
  const location = useLocation();
  if (!isLoggedIn()) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const handleAuthExpired = () => {
      navigate("/login", { replace: true, state: { from: location } });
    };
    window.addEventListener("mathbank:auth-expired", handleAuthExpired);
    return () => window.removeEventListener("mathbank:auth-expired", handleAuthExpired);
  }, [location, navigate]);

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/request" element={<RequireAuth><RequestPaper /></RequireAuth>} />
      <Route path="/generating/:quizId" element={<RequireAuth><GeneratingPaper /></RequireAuth>} />
      <Route path="/exam/:quizId" element={<RequireAuth><TakeExam /></RequireAuth>} />
      <Route path="/exam/:quizId/review" element={<RequireAuth><Review /></RequireAuth>} />
    </Routes>
  );
}
