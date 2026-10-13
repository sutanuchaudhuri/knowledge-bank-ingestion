import { Navigate, Route, Routes } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Signup from "./pages/Signup.jsx";
import Login from "./pages/Login.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import RequestPaper from "./pages/RequestPaper.jsx";
import TakeExam from "./pages/TakeExam.jsx";
import Review from "./pages/Review.jsx";
import { isLoggedIn } from "./api.js";

function RequireAuth({ children }) {
  if (!isLoggedIn()) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/request" element={<RequireAuth><RequestPaper /></RequireAuth>} />
      <Route path="/exam/:quizId" element={<RequireAuth><TakeExam /></RequireAuth>} />
      <Route path="/exam/:quizId/review" element={<RequireAuth><Review /></RequireAuth>} />
    </Routes>
  );
}
