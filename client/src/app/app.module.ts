import { APP_INITIALIZER, DoBootstrap, Injector, NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';

import { AppComponent } from './app.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { TranslocoRootModule } from './transloco-root.module';
import { ApiModule } from './api/api.module';
import { createCustomElement } from '@angular/elements';

import { AppCommonModule } from './common/app-common.module';
import { BaseUrlInterceptor } from './common/interceptors/base-url.interceptor';
import { ComponentsModule } from './components/components.module';
import { CallingModule } from './calling/calling.module';
import { RetryInterceptor } from './common/interceptors/retry.interceptor';
import { TimeoutInterceptor } from './common/interceptors/timeout.interceptor';
import { AuthInterceptor } from './common/interceptors/auth.interceptor';
import { ApiService } from './api/services';
import { ConfigService } from './services/config/config.service';
import { AppInitializationService } from './services/app-initialization/app-initialization.service';

function initializeApp(appInitializationService: AppInitializationService) {
  return appInitializationService.initialize()
}

@NgModule({
  declarations: [
    AppComponent,
  ],
  imports: [
    BrowserModule,
    BrowserAnimationsModule,
    HttpClientModule,
    TranslocoRootModule,
    ApiModule.forRoot({ rootUrl: '' }),
    AppCommonModule,
    ComponentsModule,
    CallingModule,
  ],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: BaseUrlInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: RetryInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: TimeoutInterceptor, multi: true },
    { provide: APP_INITIALIZER, useFactory: (i: AppInitializationService) => initializeApp(i), deps: [ AppInitializationService ] }
  ],
  bootstrap: [],
})
export class AppModule implements DoBootstrap {
  constructor(private readonly injector: Injector) {}

  ngDoBootstrap() {
    const app = createCustomElement(AppComponent, { injector: this.injector });
    customElements.define('dear-mep', app);
  }
}


