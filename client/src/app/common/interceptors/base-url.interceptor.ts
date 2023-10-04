import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor
} from '@angular/common/http';
import { mergeMap, Observable } from 'rxjs';
import { BaseUrlService } from '../services/base-url.service';
import { UrlUtil } from '../util/url.util';

/**
 * Detects requests to relative urls and prefixes them with a base-url
 */
@Injectable()
export class BaseUrlInterceptor implements HttpInterceptor {
  constructor(private readonly baseUrlService: BaseUrlService) { }

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    // leave absolute urls unchanged
    if (UrlUtil.isAbsolute(request.url)) {
      return next.handle(request);
    }

    // prefix relative urls
    return this.baseUrlService.toAbsoluteAPIUrl$(request.url).pipe(
      mergeMap(absoluteUrl =>
        next.handle(
          request.clone({ url: absoluteUrl })
        )
      )
    )
  }
}
