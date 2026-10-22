package com.olamidepanel.digimarketing;
import android.app.*;import android.os.Bundle;import android.webkit.*;import android.net.Uri;import android.content.Intent;
public class MainActivity extends Activity {
 private WebView web;
 @Override public void onCreate(Bundle state){super.onCreate(state);web=new WebView(this);setContentView(web);web.setBackgroundColor(0xff0b1020);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
 web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){Uri u=request.getUrl();if("https".equals(u.getScheme())&&"digimarketing.olamidepanel.com".equals(u.getHost()))return false;if("https".equals(u.getScheme()))startActivity(new Intent(Intent.ACTION_VIEW,u));return true;}@Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame())new AlertDialog.Builder(MainActivity.this).setTitle("DigiMarketing is unavailable").setMessage("Check your connection and try again.").setPositiveButton("Retry",(d,w)->web.loadUrl("https://digimarketing.olamidepanel.com/")).setNegativeButton("Close",null).show();}});
 web.setDownloadListener((url,ua,cd,mime,len)->{Uri u=Uri.parse(url);if("https".equals(u.getScheme()))startActivity(new Intent(Intent.ACTION_VIEW,u));});web.loadUrl("https://digimarketing.olamidepanel.com/");}
 @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
 @Override protected void onPause(){CookieManager.getInstance().flush();super.onPause();}
}
