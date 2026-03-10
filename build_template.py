"""Build the email template with embedded base64 logo and favicon."""
import base64

with open("config/email_templates/logo/Logo.png", "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode()

with open("config/email_templates/logo/favicon.ico", "rb") as f:
    favicon_b64 = base64.b64encode(f.read()).decode()

template = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f0f2f5; font-family:'Segoe UI', Arial, sans-serif;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
<tr><td align="center">

<!-- Main Card -->
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,0.08);">

<!-- Header Banner with Logo -->
<tr>
<td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding:25px 40px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:middle;">
<img src="data:image/png;base64,{logo_b64}" alt="Axenora AI" style="height:45px; display:block;" />
</td>
</tr>
<tr>
<td style="padding-top:15px;">
<span style="font-size:24px; font-weight:700; color:#ffffff; line-height:1.3;">Your AI Receptionist is Ready</span>
</td>
</tr>
</table>
</td>
</tr>

<!-- Body -->
<tr>
<td style="padding:35px 40px;">

<!-- Greeting -->
<p style="margin:0 0 20px; font-size:16px; color:#1a1a2e; line-height:1.6;">
Hi <strong>{{{{ business_name }}}}</strong>,
</p>

<p style="margin:0 0 20px; font-size:15px; color:#444; line-height:1.7;">
I came across {{{{ business_name }}}} in {{{{ city }}}} and was impressed! Quick thought &#8212; how many phone orders and reservations slip through when lines are busy or after hours?
</p>

<p style="margin:0 0 15px; font-size:15px; color:#444; line-height:1.7;">
We built an <strong style="color:#5b21b6;">AI Receptionist</strong> that solves this completely:
</p>

<!-- Features -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 25px;">
<tr>
<td style="padding:12px 16px; background:#f8f7ff; border-radius:8px; border-left:4px solid #7c3aed;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="font-size:20px; padding-right:12px; vertical-align:top;">&#128222;</td>
<td style="font-size:14px; color:#333; line-height:1.5;"><strong>Answers every call 24/7</strong><br><span style="color:#666;">Never miss an order or reservation again</span></td>
</tr></table>
</td>
</tr>
<tr><td style="height:8px;"></td></tr>
<tr>
<td style="padding:12px 16px; background:#f0fdf4; border-radius:8px; border-left:4px solid #22c55e;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="font-size:20px; padding-right:12px; vertical-align:top;">&#127860;</td>
<td style="font-size:14px; color:#333; line-height:1.5;"><strong>Takes orders automatically</strong><br><span style="color:#666;">Sends them straight to your kitchen</span></td>
</tr></table>
</td>
</tr>
<tr><td style="height:8px;"></td></tr>
<tr>
<td style="padding:12px 16px; background:#eff6ff; border-radius:8px; border-left:4px solid #3b82f6;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="font-size:20px; padding-right:12px; vertical-align:top;">&#128197;</td>
<td style="font-size:14px; color:#333; line-height:1.5;"><strong>Handles table reservations</strong><br><span style="color:#666;">No more putting customers on hold</span></td>
</tr></table>
</td>
</tr>
<tr><td style="height:8px;"></td></tr>
<tr>
<td style="padding:12px 16px; background:#fefce8; border-radius:8px; border-left:4px solid #eab308;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="font-size:20px; padding-right:12px; vertical-align:top;">&#129302;</td>
<td style="font-size:14px; color:#333; line-height:1.5;"><strong>Sounds completely natural</strong><br><span style="color:#666;">Customers won&#39;t know it&#39;s AI</span></td>
</tr></table>
</td>
</tr>
</table>

<!-- Stats callout -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 25px;">
<tr>
<td style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius:10px; padding:20px 25px; text-align:center;">
<span style="font-size:28px; font-weight:800; color:#fff;">30-40%</span>
<br>
<span style="font-size:14px; color:rgba(255,255,255,0.9);">more orders within the first month</span>
</td>
</tr>
</table>

<p style="margin:0 0 25px; font-size:15px; color:#444; line-height:1.7;">
Would love to show you a quick 10-minute demo for {{{{ business_name }}}}.
</p>

<!-- CTA Button -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td align="center">
<a href="{{{{ calendar_link }}}}" style="display:inline-block; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#ffffff; padding:14px 36px; text-decoration:none; border-radius:8px; font-size:16px; font-weight:700; letter-spacing:0.5px;">
Book a Free Demo &#8594;
</a>
</td>
</tr>
</table>

<p style="margin:20px 0 0; font-size:14px; color:#888; text-align:center;">
Or just reply to this email &#8212; happy to chat!
</p>

</td>
</tr>

<!-- Divider -->
<tr>
<td style="padding:0 40px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td style="border-top:1px solid #eee;"></td></tr></table>
</td>
</tr>

<!-- Footer / Signature -->
<tr>
<td style="padding:25px 40px 35px;">
<table cellpadding="0" cellspacing="0">
<tr>
<td style="padding-right:15px; vertical-align:top;">
<img src="data:image/x-icon;base64,{favicon_b64}" alt="K" style="width:44px; height:44px; border-radius:50%; display:block;" />
</td>
<td style="vertical-align:top;">
<strong style="font-size:15px; color:#1a1a2e;">{{{{ sender_name }}}}</strong><br>
<span style="font-size:13px; color:#666;">{{{{ sender_company }}}}</span><br>
<span style="font-size:13px; color:#666;">{{{{ sender_phone }}}}</span><br>
<a href="{{{{ sender_website }}}}" style="font-size:13px; color:#7c3aed; text-decoration:none;">{{{{ sender_website }}}}</a>
</td>
</tr>
</table>
</td>
</tr>

</table>
<!-- End Main Card -->

</td></tr>
</table>
<!-- End Wrapper -->

</body>
</html>'''

with open("config/email_templates/template_restaurant.html", "w", encoding="utf-8") as f:
    f.write(template)

print("Template built with embedded logo + favicon!")
