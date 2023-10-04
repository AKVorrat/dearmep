import { Injectable } from '@angular/core';
import { BehaviorSubject, filter, map, Observable } from 'rxjs';
import { UrlUtil } from '../util/url.util';

/**
 * This service helps to convert urls that are supposed to be relative to the backend of this application
 * into absolute urls.
 * Since the brownsers behavior is to treate all relative urls as if they were referencing to the embedding
 * host-page it is necessary to convert relative urls to absolute using a configurable base-url.
 */
@Injectable({
  providedIn: 'root'
})
export class BaseUrlService {
  private readonly assetsUrl$ = new BehaviorSubject<string | undefined>(undefined)
  private readonly apiUrl$ = new BehaviorSubject<string | undefined>(undefined)

  public setAssetsUrl(url: string) {
    this.assetsUrl$.next(url)
  }

  public setAPIUrl(url: string) {
    this.apiUrl$.next(url)
  }

  public getAssetsUrl$(): Observable<string> {
    return this.assetsUrl$
      .pipe(filter(u => !!u)) as Observable<string>
  }

  public getAPIUrl$(): Observable<string> {
    return this.apiUrl$
      .pipe(filter(u => !!u)) as Observable<string>
  }

  public toAbsoluteAssetUrl$(relativeUrl: string) {
    return this.toAbsoluteUrl$(relativeUrl, this.assetsUrl$)
  }

  public toAbsoluteAssetUrl(relativeUrl: string) {
    return this.toAbsoluteUrl(relativeUrl, this.assetsUrl$.value)
  }

  public toAbsoluteAPIUrl$(relativeUrl: string) {
    return this.toAbsoluteUrl$(relativeUrl, this.apiUrl$)
  }

  public toAbsoluteAPIUrl(relativeUrl: string) {
    return this.toAbsoluteUrl(relativeUrl, this.apiUrl$.value)
  }

  private toAbsoluteUrl$(relativeUrl: string, baseUrl$: Observable<string | undefined>): Observable<string> {
    if (UrlUtil.isAbsolute(relativeUrl)) {
      return new BehaviorSubject(relativeUrl)
    }

    return baseUrl$.pipe(
      filter(u => !!u),
      map(baseUrl => UrlUtil.toAbsolute(relativeUrl, baseUrl))
    )
  }

  private toAbsoluteUrl(relativeUrl: string, baseUrl: string | undefined): string {
    if (UrlUtil.isAbsolute(relativeUrl)) {
      return relativeUrl
    }

    return UrlUtil.toAbsolute(relativeUrl, baseUrl)
  }
}
