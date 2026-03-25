# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please report it responsibly:

1. **Email**: Send details to [openvort@openvort.com](mailto:openvort@openvort.com)
2. **Subject**: Include "SECURITY" in the subject line
3. **Details**: Provide as much information as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix & disclosure**: We aim to resolve critical issues within 30 days

### What to Expect

- We will acknowledge receipt of your report
- We will investigate and validate the issue
- We will work on a fix and coordinate disclosure
- We will credit you in the security advisory (unless you prefer anonymity)

## Security Best Practices for Deployment

- **Never** use default passwords in production
- **Always** set a strong `OPENVORT_LLM_API_KEY` and database password
- Configure `CORS` origins instead of using wildcard (`*`)
- Use HTTPS in production with a reverse proxy (e.g., Nginx)
- Restrict database access to trusted networks
- Regularly rotate API keys and tokens
