import GlassPane from "../../components/GlassPane";
import InputSection from "../../components/InputSection";
import ButtonPrimary from "../../components/ButtonPrimary";
import { apiClient, backendClient, getApiErrorMessage } from "../../services/apiClient";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import type { ApiUser } from "../../types/api.types";
import { mapApiUser } from "../../services/api";
import { useToast } from "../../context/useToast";

function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const { showToast } = useToast();
    const initialError = (location.state as { authError?: string } | null)?.authError;

    useEffect(() => {
        if (initialError) showToast(initialError, "error");
    }, [initialError, showToast]);

    const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        try {
            const { data: tokens } = await apiClient.post<{
                access_token: string;
                refresh_token: string;
            }>('/auth/login', { email, password });
            const { data: profile } = await backendClient.get<ApiUser>('/api/v1/auth/me', {
                headers: { Authorization: `Bearer ${tokens.access_token}` },
            });
            login(tokens.access_token, tokens.refresh_token, mapApiUser(profile));
            showToast("Signed in successfully.", "success");
            navigate('/');

        } catch (err: unknown) {
            showToast(getApiErrorMessage(err, 'Could not connect to the backend.'), "error");
        }
    }
    return (
        <GlassPane className="flex items-center justify-center min-h-[490px] w-full max-w-[342px] flex-col items-stretch px-[33px] pb-[30px] pt-[38px]">
            <div className="flex h-11 items-center justify-center gap-1.5" aria-label="NeuroTrace">
                <img className="h-11 w-11 object-contain" src="/favicon-light.svg" alt="" />
                <span
                    className="inline-block bg-clip-text font-heading text-[30px] font-extrabold leading-none tracking-[-0.7px] text-transparent"
                    style={{
                        backgroundImage: "linear-gradient(96deg, #08A984 0%, #01194A 100%)",
                        backgroundPosition: "-6px -4px",
                        backgroundSize: "calc(100% + 12px) calc(100% + 10px)",
                    }}
                >
                    NeuroTrace
                </span>
            </div>

            <h1 className="mt-[55px] text-center font-heading text-[36px] font-extrabold leading-[1.15] tracking-[-0.4px] text-[#06234e]">
                SIGN IN
            </h1>

            <form
                className="mt-[48px] flex flex-col gap-[18px]"
                onSubmit={handleLogin}
            >
                <InputSection
                    label="Email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder="Email address"
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
                <InputSection
                    autoComplete="current-password"
                    label="Password"
                    name="password"
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Password"
                    required
                    type="password"
                    value={password}
                />
                <ButtonPrimary className="w-full" type="submit">SIGN IN</ButtonPrimary>
            </form>
        </GlassPane>
    );
}
import { useAuth } from "../../context/useAuth";
import { useNavigate } from "react-router-dom";

export default LoginPage;
