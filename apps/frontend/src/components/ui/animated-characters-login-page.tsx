"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest, roleToLabel, type ApiUser } from "@/lib/api-client";
import { getLocalStorageValue, setLocalStorageValue } from "@/lib/local-storage.client";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Eye, EyeOff, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";

const REMEMBER_PREFERENCE_KEY = "ai-testing.auth.remember";

interface PupilProps {
  size?: number;
  maxDistance?: number;
  pupilColor?: string;
  forceLookX?: number;
  forceLookY?: number;
}

function Pupil({ size = 12, maxDistance = 5, pupilColor = "black", forceLookX, forceLookY }: PupilProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const pupilRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const calculatePupilPosition = () => {
    if (!pupilRef.current) {
      return { x: 0, y: 0 };
    }

    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }

    const pupil = pupilRef.current.getBoundingClientRect();
    const pupilCenterX = pupil.left + pupil.width / 2;
    const pupilCenterY = pupil.top + pupil.height / 2;
    const deltaX = mouseX - pupilCenterX;
    const deltaY = mouseY - pupilCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);
    const angle = Math.atan2(deltaY, deltaX);

    return {
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
    };
  };

  const pupilPosition = calculatePupilPosition();

  return (
    <div
      className="rounded-full"
      ref={pupilRef}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        backgroundColor: pupilColor,
        transform: `translate(${pupilPosition.x}px, ${pupilPosition.y}px)`,
        transition: "transform 0.1s ease-out",
      }}
    />
  );
}

interface EyeBallProps {
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
}

function EyeBall({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = "white",
  pupilColor = "black",
  isBlinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const eyeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const calculatePupilPosition = () => {
    if (!eyeRef.current) {
      return { x: 0, y: 0 };
    }

    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }

    const eye = eyeRef.current.getBoundingClientRect();
    const eyeCenterX = eye.left + eye.width / 2;
    const eyeCenterY = eye.top + eye.height / 2;
    const deltaX = mouseX - eyeCenterX;
    const deltaY = mouseY - eyeCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);
    const angle = Math.atan2(deltaY, deltaX);

    return {
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
    };
  };

  const pupilPosition = calculatePupilPosition();

  return (
    <div
      className="flex items-center justify-center overflow-hidden rounded-full transition-all duration-150"
      ref={eyeRef}
      style={{
        width: `${size}px`,
        height: isBlinking ? "2px" : `${size}px`,
        backgroundColor: eyeColor,
      }}
    >
      {!isBlinking && (
        <div
          className="rounded-full"
          style={{
            width: `${pupilSize}px`,
            height: `${pupilSize}px`,
            backgroundColor: pupilColor,
            transform: `translate(${pupilPosition.x}px, ${pupilPosition.y}px)`,
            transition: "transform 0.1s ease-out",
          }}
        />
      )}
    </div>
  );
}

function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((state) => state.login);
  const [showPassword, setShowPassword] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false);
  const [isBlackBlinking, setIsBlackBlinking] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false);
  const [isPurplePeeking, setIsPurplePeeking] = useState(false);
  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRemember(getLocalStorageValue(REMEMBER_PREFERENCE_KEY) === "true");
  }, []);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    const scheduleBlink = () => {
      const blinkTimeout = window.setTimeout(
        () => {
          setIsPurpleBlinking(true);
          window.setTimeout(() => {
            setIsPurpleBlinking(false);
            scheduleBlink();
          }, 150);
        },
        Math.random() * 4000 + 3000
      );

      return blinkTimeout;
    };

    const timeout = scheduleBlink();
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    const scheduleBlink = () => {
      const blinkTimeout = window.setTimeout(
        () => {
          setIsBlackBlinking(true);
          window.setTimeout(() => {
            setIsBlackBlinking(false);
            scheduleBlink();
          }, 150);
        },
        Math.random() * 4000 + 3000
      );

      return blinkTimeout;
    };

    const timeout = scheduleBlink();
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (!isTyping) {
      setIsLookingAtEachOther(false);
      return;
    }

    setIsLookingAtEachOther(true);
    const timer = window.setTimeout(() => setIsLookingAtEachOther(false), 800);
    return () => window.clearTimeout(timer);
  }, [isTyping]);

  useEffect(() => {
    if (!(password.length > 0 && showPassword)) {
      setIsPurplePeeking(false);
      return;
    }

    const peekInterval = window.setTimeout(
      () => {
        setIsPurplePeeking(true);
        window.setTimeout(() => setIsPurplePeeking(false), 800);
      },
      Math.random() * 3000 + 2000
    );

    return () => window.clearTimeout(peekInterval);
  }, [password, showPassword, isPurplePeeking]);

  const calculatePosition = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (!ref.current) {
      return { faceX: 0, faceY: 0, bodySkew: 0 };
    }

    const rect = ref.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 3;
    const deltaX = mouseX - centerX;
    const deltaY = mouseY - centerY;

    return {
      faceX: Math.max(-15, Math.min(15, deltaX / 20)),
      faceY: Math.max(-10, Math.min(10, deltaY / 30)),
      bodySkew: Math.max(-6, Math.min(6, -deltaX / 120)),
    };
  };

  const purplePos = calculatePosition(purpleRef);
  const blackPos = calculatePosition(blackRef);
  const yellowPos = calculatePosition(yellowRef);
  const orangePos = calculatePosition(orangeRef);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const result = await apiRequest<{ access_token: string; current_user: ApiUser }>("/auth/login", {
        body: JSON.stringify({ password, username }),
        method: "POST",
      });
      login({
        token: result.access_token,
        remember,
        user: {
          email: result.current_user.email,
          name: result.current_user.username,
          role: result.current_user.role,
        },
      });
      toast.success("登录成功", {
        description: `已以${roleToLabel(result.current_user.role)}身份进入 AI 测试系统。`,
      });
      router.replace(searchParams.get("next") || "/dashboard");
    } catch (error) {
      setError(error instanceof Error ? error.message : "账号或密码不正确，请联系管理员确认账号状态。");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRememberChange = (checked: boolean) => {
    setRemember(checked);
    setLocalStorageValue(REMEMBER_PREFERENCE_KEY, checked ? "true" : "false");
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-primary p-12 text-primary-foreground lg:flex">
        <div className="relative z-20">
          <div className="flex items-center gap-2 font-semibold text-lg">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary-foreground/10 backdrop-blur-sm">
              <Sparkles className="size-4" />
            </div>
            <span>AI 测试系统</span>
          </div>
        </div>

        <div className="relative z-20 flex h-[500px] items-end justify-center">
          <div className="relative" style={{ width: "550px", height: "400px" }}>
            <div
              className="absolute bottom-0 transition-all duration-700 ease-in-out"
              ref={purpleRef}
              style={{
                left: "70px",
                width: "180px",
                height: isTyping || (password.length > 0 && !showPassword) ? "440px" : "400px",
                backgroundColor: "#6C3FF5",
                borderRadius: "10px 10px 0 0",
                zIndex: 1,
                transform:
                  password.length > 0 && showPassword
                    ? "skewX(0deg)"
                    : isTyping || (password.length > 0 && !showPassword)
                      ? `skewX(${purplePos.bodySkew - 12}deg) translateX(40px)`
                      : `skewX(${purplePos.bodySkew}deg)`,
                transformOrigin: "bottom center",
              }}
            >
              <div
                className="absolute flex gap-8 transition-all duration-700 ease-in-out"
                style={{
                  left: password.length > 0 && showPassword ? "20px" : isLookingAtEachOther ? "55px" : `${45 + purplePos.faceX}px`,
                  top: password.length > 0 && showPassword ? "35px" : isLookingAtEachOther ? "65px" : `${40 + purplePos.faceY}px`,
                }}
              >
                <EyeBall
                  eyeColor="white"
                  forceLookX={password.length > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
                  forceLookY={password.length > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
                  isBlinking={isPurpleBlinking}
                  maxDistance={5}
                  pupilColor="#2D2D2D"
                  pupilSize={7}
                  size={18}
                />
                <EyeBall
                  eyeColor="white"
                  forceLookX={password.length > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
                  forceLookY={password.length > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
                  isBlinking={isPurpleBlinking}
                  maxDistance={5}
                  pupilColor="#2D2D2D"
                  pupilSize={7}
                  size={18}
                />
              </div>
            </div>

            <div
              className="absolute bottom-0 transition-all duration-700 ease-in-out"
              ref={blackRef}
              style={{
                left: "240px",
                width: "120px",
                height: "310px",
                backgroundColor: "#2D2D2D",
                borderRadius: "8px 8px 0 0",
                zIndex: 2,
                transform:
                  password.length > 0 && showPassword
                    ? "skewX(0deg)"
                    : isLookingAtEachOther
                      ? `skewX(${blackPos.bodySkew * 1.5 + 10}deg) translateX(20px)`
                      : isTyping || (password.length > 0 && !showPassword)
                        ? `skewX(${blackPos.bodySkew * 1.5}deg)`
                        : `skewX(${blackPos.bodySkew}deg)`,
                transformOrigin: "bottom center",
              }}
            >
              <div
                className="absolute flex gap-6 transition-all duration-700 ease-in-out"
                style={{
                  left: password.length > 0 && showPassword ? "10px" : isLookingAtEachOther ? "32px" : `${26 + blackPos.faceX}px`,
                  top: password.length > 0 && showPassword ? "28px" : isLookingAtEachOther ? "12px" : `${32 + blackPos.faceY}px`,
                }}
              >
                <EyeBall
                  eyeColor="white"
                  forceLookX={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
                  isBlinking={isBlackBlinking}
                  maxDistance={4}
                  pupilColor="#2D2D2D"
                  pupilSize={6}
                  size={16}
                />
                <EyeBall
                  eyeColor="white"
                  forceLookX={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
                  isBlinking={isBlackBlinking}
                  maxDistance={4}
                  pupilColor="#2D2D2D"
                  pupilSize={6}
                  size={16}
                />
              </div>
            </div>

            <div
              className="absolute bottom-0 transition-all duration-700 ease-in-out"
              ref={orangeRef}
              style={{
                left: "0px",
                width: "240px",
                height: "200px",
                zIndex: 3,
                backgroundColor: "#FF9B6B",
                borderRadius: "120px 120px 0 0",
                transform: password.length > 0 && showPassword ? "skewX(0deg)" : `skewX(${orangePos.bodySkew}deg)`,
                transformOrigin: "bottom center",
              }}
            >
              <div
                className="absolute flex gap-8 transition-all duration-200 ease-out"
                style={{
                  left: password.length > 0 && showPassword ? "50px" : `${82 + orangePos.faceX}px`,
                  top: password.length > 0 && showPassword ? "85px" : `${90 + orangePos.faceY}px`,
                }}
              >
                <Pupil forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} pupilColor="#2D2D2D" />
                <Pupil forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} pupilColor="#2D2D2D" />
              </div>
            </div>

            <div
              className="absolute bottom-0 transition-all duration-700 ease-in-out"
              ref={yellowRef}
              style={{
                left: "310px",
                width: "140px",
                height: "230px",
                backgroundColor: "#E8D754",
                borderRadius: "70px 70px 0 0",
                zIndex: 4,
                transform: password.length > 0 && showPassword ? "skewX(0deg)" : `skewX(${yellowPos.bodySkew}deg)`,
                transformOrigin: "bottom center",
              }}
            >
              <div
                className="absolute flex gap-6 transition-all duration-200 ease-out"
                style={{
                  left: password.length > 0 && showPassword ? "20px" : `${52 + yellowPos.faceX}px`,
                  top: password.length > 0 && showPassword ? "35px" : `${40 + yellowPos.faceY}px`,
                }}
              >
                <Pupil forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} pupilColor="#2D2D2D" />
                <Pupil forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} pupilColor="#2D2D2D" />
              </div>
              <div
                className="absolute h-[4px] w-20 rounded-full bg-[#2D2D2D] transition-all duration-200 ease-out"
                style={{
                  left: password.length > 0 && showPassword ? "10px" : `${40 + yellowPos.faceX}px`,
                  top: password.length > 0 && showPassword ? "88px" : `${88 + yellowPos.faceY}px`,
                }}
              />
            </div>
          </div>
        </div>

        <div />
      </div>

      <div className="flex items-center justify-center bg-background p-8">
        <div className="w-full max-w-[420px]">
          <div className="mb-12 flex items-center justify-center gap-2 font-semibold text-lg lg:hidden">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10">
              <Sparkles className="size-4 text-primary" />
            </div>
            <span>AI 测试系统</span>
          </div>

          <div className="mb-10 text-center">
            <h1 className="mb-2 font-bold text-3xl tracking-tight">欢迎回来</h1>
          </div>

          <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-2">
              <Label htmlFor="login-username">用户名</Label>
              <Input
                autoComplete="username"
                className="h-12 border-border/60 bg-background focus:border-primary"
                id="login-username"
                onBlur={() => setIsTyping(false)}
                onChange={(event) => setUsername(event.target.value)}
                onFocus={() => setIsTyping(true)}
                placeholder="admin"
                required
                type="text"
                value={username}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="login-password">密码</Label>
              <div className="relative">
                <Input
                  autoComplete="current-password"
                  className="h-12 border-border/60 bg-background pr-10 focus:border-primary"
                  id="login-password"
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="请输入密码"
                  required
                  type={showPassword ? "text" : "password"}
                  value={password}
                />
                <button
                  className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => setShowPassword((value) => !value)}
                  type="button"
                >
                  {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center">
              <div className="flex items-center gap-2">
                <Checkbox checked={remember} id="login-remember" onCheckedChange={(checked) => handleRememberChange(Boolean(checked))} />
                <Label className="cursor-pointer font-normal" htmlFor="login-remember">
                  记住登录状态
                </Label>
              </div>
            </div>

            {error && <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-destructive text-sm">{error}</div>}

            <Button className="h-12 w-full font-medium text-base" disabled={isLoading} size="lg" type="submit">
              {isLoading ? "正在登录..." : "登录"}
            </Button>
          </form>

          <div className="mt-6">
            <Button className="h-12 w-full border-border/60 bg-background hover:bg-accent" disabled type="button" variant="outline">
              <Mail className="mr-2 size-5" />
              第三方登录暂未开放
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export const Component = LoginPage;
