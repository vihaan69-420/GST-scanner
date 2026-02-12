/**
 * Send OTP by email (Resend free tier) and SMS (Twilio trial).
 * If env vars are missing, OTP is logged to console for testing.
 */

const OTP_EXPIRY_MINUTES = 10;

export function generateOtp(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

export function getOtpExpiryMinutes(): number {
  return OTP_EXPIRY_MINUTES;
}

export async function sendEmailOtp(email: string, otp: string): Promise<{ sent: boolean; error?: string }> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.log("[OTP] No RESEND_API_KEY — OTP for", email, ":", otp);
    return { sent: true };
  }
  try {
    const { Resend } = await import("resend");
    const resend = new Resend(apiKey);
    const from = process.env.RESEND_FROM_EMAIL || "onboarding@resend.dev";
    const text = `Your verification code is: ${otp}. It expires in ${OTP_EXPIRY_MINUTES} minutes.`;
    const { error } = await resend.emails.send({
      from: from,
      to: email,
      subject: "Your verification code — GST Scanner",
      text,
      html: `<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;"><h2 style="color:#333;">Your verification code</h2><p>Your verification code is: <strong style="font-size:1.25em;letter-spacing:0.1em;">${otp}</strong></p><p>It expires in ${OTP_EXPIRY_MINUTES} minutes.</p><p style="color:#666;font-size:0.875em;">— GST Scanner</p></body></html>`,
    });
    if (error) {
      console.error("[OTP] Resend error:", error);
      return { sent: false, error: error.message };
    }
    return { sent: true };
  } catch (e) {
    console.error("[OTP] sendEmailOtp", e);
    return { sent: false, error: e instanceof Error ? e.message : "Failed to send email" };
  }
}

export async function sendSmsOtp(phone: string, otp: string): Promise<{ sent: boolean; error?: string }> {
  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  const fromNumber = process.env.TWILIO_PHONE_NUMBER;
  if (!accountSid || !authToken || !fromNumber) {
    console.log("[OTP] No Twilio config — SMS OTP for", phone, ":", otp);
    return { sent: true };
  }
  try {
    const twilio = (await import("twilio")).default;
    const client = twilio(accountSid, authToken);
    await client.messages.create({
      body: `Your GST Scanner verification code is: ${otp}. Valid for ${OTP_EXPIRY_MINUTES} minutes.`,
      from: fromNumber,
      to: phone,
    });
    return { sent: true };
  } catch (e) {
    console.error("[OTP] sendSmsOtp", e);
    return { sent: false, error: e instanceof Error ? e.message : "Failed to send SMS" };
  }
}
