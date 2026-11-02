import { createContext } from "react";
import type { AuthContextType } from "../types/authContext.types";

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
