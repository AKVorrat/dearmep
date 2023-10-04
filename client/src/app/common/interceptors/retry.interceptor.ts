import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor,
  HttpErrorResponse
} from '@angular/common/http';
import { Observable, TimeoutError, delay, of, retry, throwError } from 'rxjs';

@Injectable()
export class RetryInterceptor implements HttpInterceptor {
  private readonly rateLimitMinRetryInterval = 1000
  private readonly rateLimitMaxRetries = 20

  private readonly serverErrorRetryInterval = 1000
  private readonly serverErrorMaxRetries = 5

  private readonly timeoutRetryInterval = 0
  private readonly timeoutMaxRetries = 3

  private readonly connectionErrorInterval = 1000
  private readonly connectionErrorMaxRetries = 5

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      retry({
        delay: (error: HttpErrorResponse | TimeoutError | unknown, retryCount: number) => this.shouldRetry(error, retryCount)
      })
    );
  }

  private shouldRetry(error: HttpErrorResponse | TimeoutError | unknown, retryCount: number) {
    if (error instanceof HttpErrorResponse) {
      const httpError: HttpErrorResponse = error

      if (httpError.status === 429) {
        const retryDelay = this.getRetryAfter(httpError, this.rateLimitMinRetryInterval)
        return this.shouldRetryAfter(error, retryCount, this.rateLimitMaxRetries, retryDelay, "Server-Rate-Limit", httpError.url)
      } else if (httpError.status >= 500 && httpError.status < 600) {
        return this.shouldRetryAfter(error, retryCount, this.serverErrorMaxRetries, this.serverErrorRetryInterval, "Server-Error", httpError.url)
      } else {
        return this.fail(error) // all response errors, such as 4xx => fail without retry
      }

    } else if (error instanceof TimeoutError && error.name === "TimeoutError") {
        return this.shouldRetryAfter(error, retryCount, this.timeoutMaxRetries, this.timeoutRetryInterval, "Timeout-Error")
    } else {
      return this.shouldRetryAfter(error, retryCount, this.connectionErrorMaxRetries, this.connectionErrorInterval)
    }
  }

  private shouldRetryAfter(error: unknown, retryCount: number, maxRetryCount: number, retryInterval: number, errorName = "HttpError", url: string | null = "unknown") {
    if (retryCount > maxRetryCount) {
      console.error(`${errorName} encountered. Reached max retreis. Failing! (url: ${url}).`)
      return this.fail(error)
    }
    console.error(`${errorName} encountered. Retrying after ${retryInterval / 1000.0}s (url: ${url}).`)
    return this.reatryAfter(retryInterval)
  }

  private getRetryAfter(error: HttpErrorResponse, minRetryAfter: number): number {
    const retryAfterHeader = error.headers.get("retry-after")

    let retryAfter = parseFloat(retryAfterHeader || '') * 1000

    if (isNaN(retryAfter)) {
      retryAfter = this.rateLimitMinRetryInterval
    }

    return Math.max(retryAfter, minRetryAfter)
  }

  private reatryAfter(timeout: number): Observable<void> {
    return of(undefined).pipe(delay(timeout))
  }

  private fail(error: unknown): Observable<void> {
    return throwError(() => error)
  }
}
