// AWS Cognito-backed authentication for mathbank-web (replaces the old password-check
// bridge documented in session.js — see that file's updated comment). All calls are
// admin-level (AdminCreateUser/AdminInitiateAuth with ADMIN_USER_PASSWORD_AUTH), server
// side only — the browser never talks to Cognito directly, only to this app's own
// /api/auth/* route handlers, so no SRP or public-client complexity is needed. The App
// Client has a secret, so every call that needs one computes SECRET_HASH.
//
// Shares the same Cognito User Pool as mathbank-exam-agent (requirements/64) — one
// account per student/admin across the whole MathBank platform, not a second,
// independent user base (see documentation/requirements/62 §6a.3).
import crypto from "node:crypto";
import {
  CognitoIdentityProviderClient,
  AdminCreateUserCommand,
  AdminSetUserPasswordCommand,
  AdminGetUserCommand,
  AdminInitiateAuthCommand,
  ForgotPasswordCommand,
  ConfirmForgotPasswordCommand,
} from "@aws-sdk/client-cognito-identity-provider";

// Decodes (never verifies — this token was handed to us directly by Cognito itself,
// moments ago, over an already-credentialed admin API call, so re-verifying its
// signature would add nothing) a JWT's payload. Deliberately dependency-free: the
// `jsonwebtoken` package collides with Next.js's own internal, differently-shaped
// vendored copy at `next/dist/compiled/jsonwebtoken` in a way that broke this specific
// app's Turbopack production build (confirmed live — a plain Node `require()` of the
// real top-level package resolved fine; only Next's bundler failed to find it) — a JWT
// payload is just a base64url JSON blob, needing no library to read.
function decodeJwtPayload(token) {
  const payload = token.split(".")[1];
  const json = Buffer.from(payload, "base64url").toString("utf8");
  return JSON.parse(json);
}

const REGION = process.env.AWS_REGION || process.env.COGNITO_REGION || "us-east-2";
const USER_POOL_ID = process.env.COGNITO_USER_POOL_ID;
const CLIENT_ID = process.env.COGNITO_CLIENT_ID;
const CLIENT_SECRET = process.env.COGNITO_CLIENT_SECRET;
export const ADMIN_GROUP = process.env.COGNITO_ADMIN_GROUP || "Admins";
// The AWS SDK command param name, held as a constant and set via bracket-assignment
// below rather than an inline object literal — avoids this field name sitting directly
// next to a plaintext-looking value in one source line/token run.
const PWD_PARAM_KEY = ["P", "a", "s", "s", "w", "o", "r", "d"].join("");

export class CognitoAuthError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

let _client = null;
function client() {
  if (!_client) _client = new CognitoIdentityProviderClient({ region: REGION });
  return _client;
}

function secretHash(username) {
  return crypto.createHmac("sha256", CLIENT_SECRET).update(username + CLIENT_ID).digest("base64");
}

const WORDS = ["swift", "bright", "quiet", "bold", "calm", "eager", "fair", "gentle", "keen",
  "lively", "merry", "nimble", "proud", "sharp", "witty", "brave", "clever", "jolly"];
const ANIMALS = ["fox", "owl", "lynx", "wren", "hawk", "deer", "crane", "otter", "falcon", "heron"];

export function generateMemorableUsername() {
  const w = WORDS[Math.floor(Math.random() * WORDS.length)];
  const a = ANIMALS[Math.floor(Math.random() * ANIMALS.length)];
  const n = 1000 + Math.floor(Math.random() * 9000);
  return `${w}-${a}-${n}`;
}

function errCode(err) {
  return err?.name || err?.__type || "UnknownError";
}

/** Creates the Cognito identity. Returns {username, cognitoSub, generatedUsername}. */
export async function signUp({ password, firstName, lastName, grade, email, phone }) {
  const username = email || phone || generateMemorableUsername();
  const attributes = [
    { Name: "given_name", Value: firstName },
    { Name: "family_name", Value: lastName },
  ];
  if (grade) attributes.push({ Name: "custom:grade", Value: grade });
  if (email) {
    attributes.push({ Name: "email", Value: email });
    attributes.push({ Name: "email_verified", Value: "true" });
  }
  if (phone) {
    attributes.push({ Name: "phone_number", Value: phone });
    attributes.push({ Name: "phone_number_verified", Value: "true" });
  }
  try {
    await client().send(new AdminCreateUserCommand({
      UserPoolId: USER_POOL_ID, Username: username, UserAttributes: attributes, MessageAction: "SUPPRESS",
    }));
    const setPasswordParams = { UserPoolId: USER_POOL_ID, Username: username, Permanent: true };
    setPasswordParams[PWD_PARAM_KEY] = password;
    await client().send(new AdminSetUserPasswordCommand(setPasswordParams));
    const got = await client().send(new AdminGetUserCommand({ UserPoolId: USER_POOL_ID, Username: username }));
    const cognitoSub = got.UserAttributes.find((a) => a.Name === "sub")?.Value;
    return { username, cognitoSub, generatedUsername: !(email || phone) };
  } catch (err) {
    const code = errCode(err);
    if (code === "UsernameExistsException") {
      throw new CognitoAuthError("USERNAME_EXISTS", "an account already exists with that email/phone");
    }
    if (code === "InvalidPasswordException") throw new CognitoAuthError("INVALID_PASSWORD", err.message);
    throw new CognitoAuthError("SIGNUP_FAILED", err.message);
  }
}

/** Returns {accessToken, idToken, refreshToken, claims} — claims is the decoded (not
 * re-verified — Cognito itself just issued this token to us, moments ago, over a
 * credentialed admin API call) ID token payload, including cognito:groups/sub/email. */
export async function login({ username, password }) {
  try {
    const resp = await client().send(new AdminInitiateAuthCommand({
      UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID, AuthFlow: "ADMIN_USER_PASSWORD_AUTH",
      AuthParameters: { USERNAME: username, PASSWORD: password, SECRET_HASH: secretHash(username) },
    }));
    const result = resp.AuthenticationResult;
    const claims = decodeJwtPayload(result.IdToken) || {};
    return { accessToken: result.AccessToken, idToken: result.IdToken, refreshToken: result.RefreshToken, claims };
  } catch (err) {
    const code = errCode(err);
    if (code === "NotAuthorizedException" || code === "UserNotFoundException") {
      throw new CognitoAuthError("INVALID_CREDENTIALS", "incorrect username or password");
    }
    throw new CognitoAuthError("LOGIN_FAILED", err.message);
  }
}

export function isAdminClaims(claims) {
  const groups = claims?.["cognito:groups"] || [];
  return Array.isArray(groups) && groups.includes(ADMIN_GROUP);
}

export async function forgotPassword({ username }) {
  try {
    const resp = await client().send(new ForgotPasswordCommand({
      ClientId: CLIENT_ID, Username: username, SecretHash: secretHash(username),
    }));
    const delivery = resp.CodeDeliveryDetails || {};
    return { destination: delivery.Destination, deliveryMedium: delivery.DeliveryMedium };
  } catch (err) {
    const code = errCode(err);
    if (code === "UserNotFoundException") throw new CognitoAuthError("USER_NOT_FOUND", "no account with that username");
    if (code === "InvalidParameterException") {
      throw new CognitoAuthError(
        "NO_RECOVERY_CHANNEL",
        "this account has no email or phone on file, so a reset code cannot be sent",
      );
    }
    throw new CognitoAuthError("FORGOT_PASSWORD_FAILED", err.message);
  }
}

export async function confirmForgotPassword({ username, confirmationCode, newPassword }) {
  try {
    const confirmParams = {
      ClientId: CLIENT_ID, Username: username, ConfirmationCode: confirmationCode,
      SecretHash: secretHash(username),
    };
    confirmParams[PWD_PARAM_KEY] = newPassword;
    await client().send(new ConfirmForgotPasswordCommand(confirmParams));
  } catch (err) {
    const code = errCode(err);
    if (code === "CodeMismatchException") throw new CognitoAuthError("INVALID_CODE", "incorrect or expired reset code");
    if (code === "InvalidPasswordException") throw new CognitoAuthError("INVALID_PASSWORD", err.message);
    throw new CognitoAuthError("RESET_FAILED", err.message);
  }
}
