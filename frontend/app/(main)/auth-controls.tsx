"use client";

import {
  SignInButton,
  SignUpButton,
  UserButton,
  useUser,
} from "@clerk/nextjs";
import { User, LogIn, UserPlus } from "lucide-react";
import { PersonalDetailsForm } from "./personal-details";

const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

function SignedInControls() {
  const { isLoaded, isSignedIn } = useUser();

  if (!isLoaded) return <span className="auth-guest-note">Account</span>;

  if (isSignedIn) {
    return (
      <div className="auth-user-control" aria-label="Your account">
        <span className="auth-user-label">Account</span>
        <UserButton>
          <UserButton.UserProfilePage 
            label="Personal Details" 
            url="personal-details" 
            labelIcon={<User size={16} />}
          >
            <PersonalDetailsForm />
          </UserButton.UserProfilePage>
        </UserButton>
      </div>
    );
  }

  return (
    <div className="auth-controls" aria-label="Account access">
      <span className="auth-guest-note">You can continue as a guest.</span>
      <SignInButton mode="modal">
        <button className="auth-button auth-button-quiet" type="button">
          <LogIn size={13} aria-hidden="true" />
          <span>Sign in</span>
        </button>
      </SignInButton>
      <SignUpButton mode="modal">
        <button className="auth-button auth-button-primary" type="button">
          <UserPlus size={13} aria-hidden="true" />
          <span>Create account</span>
        </button>
      </SignUpButton>
    </div>
  );
}

export default function AuthControls() {
  if (!clerkConfigured) {
    return <span className="auth-guest-note">Guest access</span>;
  }

  return <SignedInControls />;
}
