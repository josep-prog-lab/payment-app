# 🚀 Deployment Guide - Smart Payment Verification System

## ✅ Pre-Deployment Checklist

### 1. Supabase Setup
- [ ] Create Supabase project at [supabase.com](https://supabase.com)
- [ ] Run the SQL script from `database/schema.sql` in Supabase SQL Editor
- [ ] Copy Project URL and Anon Key from Settings > API
- [ ] Test database connection from Supabase dashboard

### 2. Environment Configuration
- [ ] Update `.env` file with your Supabase credentials
- [ ] Generate a secure SMS_FORWARDER_SECRET (use: `openssl rand -hex 32`)
- [ ] Set your business phone number in SMS_FORWARDER_NUMBER
- [ ] Verify all required environment variables are set

### 3. Code Validation
- [ ] All Python files compile without errors ✅
- [ ] Requirements.txt contains only lightweight dependencies ✅
- [ ] No scikit-learn or heavy ML dependencies ✅
- [ ] Flask app runs locally for testing

## 🌐 Render Deployment Steps

### Step 1: Connect Repository
1. Fork/clone this repository to your GitHub
2. Go to [render.com](https://render.com) and create account
3. Click "New+" and select "Web Service"
4. Connect your GitHub repository
5. Select the repository containing this code

### Step 2: Configure Service
**Build & Deploy Settings:**
- **Environment**: Python 3
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt && mkdir -p templates static`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`

### Step 3: Environment Variables
Add these environment variables in Render dashboard:

| Variable | Value | Notes |
|----------|-------|--------|
| `SUPABASE_URL` | `https://your-project.supabase.co` | From Supabase dashboard |
| `SUPABASE_KEY` | `your_anon_key` | From Supabase dashboard |
| `SMS_FORWARDER_SECRET` | `your_secure_secret` | Generate with `openssl rand -hex 32` |
| `SMS_FORWARDER_NUMBER` | `+250791646062` | Your business phone |
| `DEBUG_MODE` | `false` | Production setting |
| `LOG_LEVEL` | `INFO` | Production logging |
| `ENABLE_TEST_ENDPOINTS` | `true` | Enable for testing |
| `FRAUD_THRESHOLD` | `0.7` | Fraud detection sensitivity |

### Step 4: Deploy
1. Click "Create Web Service"
2. Wait for build to complete (should take 2-3 minutes)
3. Check logs for any errors
4. Test the health endpoint: `https://your-app.onrender.com/health`

## 📱 SMS Forwarder Setup

### Recommended Apps (Android)
1. **SMS Forwarder** (Play Store)
2. **Tasker + HTTP Request** 
3. **Webhook SMS**

### Configuration Example (SMS Forwarder)
1. Install app on business phone that receives MoMo SMS
2. Create new forwarding rule:
   - **Trigger**: Contains "Mobile Money", "Airtel Money", or "Tigo Cash"
   - **Action**: HTTP POST
   - **URL**: `https://your-app.onrender.com/api/sms`
   - **Headers**: 
     ```
     Content-Type: application/json
     X-Forwarder-Secret: your_sms_forwarder_secret
     ```
   - **Body**: 
     ```json
     {"text": "$message", "from": "$sender"}
     ```

## 🧪 Post-Deployment Testing

### 1. Health Check
```bash
curl https://your-app.onrender.com/health
```
Expected response: `{"status": "healthy", "database": "connected"}`

### 2. SMS Parsing Test
```bash
curl -X POST https://your-app.onrender.com/api/test/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "MTN Mobile Money: You received RWF 50,000.00 from JOHN DOE (0781234567). Ref: MP240815123456"}'
```

### 3. Payment Verification Test
```bash
curl -X POST https://your-app.onrender.com/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "txid": "MP240815123456",
    "name": "JOHN DOE",
    "phone": "0781234567",
    "amount": 50000
  }'
```

### 4. Web Interface Test
Visit `https://your-app.onrender.com` in browser and test:
- Payment verification form
- SMS parsing test
- Statistics dashboard

## 🚨 Troubleshooting

### Build Fails
**Issue**: Scikit-learn compilation errors
**Solution**: ✅ Already fixed - using lightweight dependencies

**Issue**: Missing templates directory
**Solution**: ✅ Already fixed - build command creates directories

### Runtime Errors
**Issue**: Supabase connection fails
**Solution**: 
- Check environment variables are set correctly
- Verify Supabase project is active
- Test connection in Supabase dashboard

**Issue**: SMS not being received
**Solution**:
- Check SMS forwarder app configuration
- Verify X-Forwarder-Secret header matches
- Test with curl command

### Performance Issues
**Issue**: Slow response times
**Solution**:
- Monitor Render metrics
- Check database query performance
- Consider upgrading Render plan

## 📊 Monitoring & Maintenance

### Health Monitoring
- Set up uptime monitoring for `/health` endpoint
- Monitor error rates in Render dashboard
- Track response times

### Database Maintenance
- Regular backup of Supabase database
- Monitor storage usage
- Clean up old test data

### Security Updates
- Rotate SMS forwarder secrets regularly
- Monitor for suspicious activity
- Update dependencies when needed

## 🔄 Scaling Considerations

### Traffic Growth
- Monitor request volume in Render
- Upgrade to higher tier if needed
- Consider adding caching layer

### Database Scaling  
- Supabase auto-scales
- Monitor connection limits
- Optimize queries if needed

## 📈 Success Metrics

After deployment, monitor these metrics:

- [ ] Health endpoint responding consistently
- [ ] SMS parsing accuracy > 90%
- [ ] Payment verification success rate > 85%
- [ ] Response times < 500ms
- [ ] Zero security incidents
- [ ] Fraud detection effectiveness

## 🎯 Go-Live Checklist

- [ ] All tests passing
- [ ] Health endpoint healthy
- [ ] SMS forwarder configured and tested
- [ ] Environment variables properly set
- [ ] Database schema deployed
- [ ] Web interface accessible
- [ ] API endpoints working
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Team trained on system

## 🆘 Emergency Contacts

If deployment fails:
1. Check Render build logs
2. Review environment variables
3. Test Supabase connection
4. Verify SMS forwarder setup
5. Contact support if needed

---

**Ready to deploy? Your Smart Payment Verification System is optimized for Render! 🚀**
