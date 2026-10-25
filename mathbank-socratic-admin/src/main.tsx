import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../../mathbank-web/app/globals.css";
import "./styles.css";
import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
