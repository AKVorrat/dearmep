import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, ReplaySubject, combineLatest, distinctUntilKeyChanged, filter, map, shareReplay, take } from 'rxjs';
import { ApiService } from 'src/app/api/services';
import { LocalStorageService } from '../local-storage/local-storage.service';
import { TranslocoService } from '@ngneat/transloco';

@Injectable({
  providedIn: 'root'
})
export class L10nService {
  private readonly languageStorageKey = "language"
  private readonly countryStorageKey = "country"

  private readonly defaultCountry$ = new ReplaySubject<string | undefined>()

  private readonly availableLanguages$ = new ReplaySubject<string[]>()
  private readonly detectedLanguage$ = new ReplaySubject<string | undefined>()
  private readonly userSelectedLanguage$: BehaviorSubject<string | undefined>

  private readonly availableCountries$ = new ReplaySubject<string[]>()
  private readonly detectedCountry$ = new ReplaySubject<string | undefined>()
  private readonly userSelectedCountry$: BehaviorSubject<string | undefined>

  private readonly randomCountry$: Observable<string>
  private readonly country$: Observable<string>

  constructor(
    private readonly apiService: ApiService,
    private readonly localStorageService: LocalStorageService,
    private readonly translocoService: TranslocoService,
  ) {
    this.userSelectedLanguage$ = new BehaviorSubject<string | undefined>(this.getStoredUserSelectedLanguage())
    this.userSelectedCountry$ = new BehaviorSubject<string | undefined>(this.getStoredUserSelectedCountry())
    this.detectUserLocalizationViaAPI()
    this.getLanguage$().subscribe({
      next(lang) { if (lang) { translocoService.setActiveLang(lang) } }
    })

    this.randomCountry$ = this.availableCountries$.pipe(
      filter(c => c?.length > 0),
      distinctUntilKeyChanged("length"),
      map((c) => c[Math.floor(c.length * Math.random())]),
      shareReplay(),
    )

    this.country$ = combineLatest([
      this.userSelectedCountry$,
      this.detectedCountry$,
      this.defaultCountry$,
      this.randomCountry$,
      this.availableCountries$,
    ]).pipe(
      map(([userSelectedCountry, apiDetectedCountry, defaultCountry, randomCountry, availableCountries]) => {
        return this.mustBePartOf(userSelectedCountry, availableCountries)
          || apiDetectedCountry
          || this.mustBePartOf(defaultCountry, availableCountries)
          || randomCountry
      }),
      shareReplay(),
    )
  }

  public getAvailableLanguages$(): Observable<string[]> {
    return this.availableLanguages$.asObservable()
  }

  public getLanguage$(): Observable<string | undefined> {
    return combineLatest([
      this.userSelectedLanguage$,
      this.detectedLanguage$,
      this.availableLanguages$,
    ]).pipe(
      map(([userSelectedLang, apiDetectedLang, availableLanguages]) => {
        return this.mustBePartOf(userSelectedLang, availableLanguages) || apiDetectedLang
      })
    )
  }

  public setLanguage(langCode: string) {
    this.localStorageService.setString(this.languageStorageKey, langCode)
    this.userSelectedLanguage$.next(langCode)
  }

  public getCountry$(): Observable<string> {
    return this.country$;
  }

  public getAvailableCountries$(): Observable<string[]> {
    return this.availableCountries$.asObservable()
  }

  public setCountry(country: string) {
    this.localStorageService.setString(this.countryStorageKey, country)
    this.userSelectedCountry$.next(country)
  }

  public setDefaultCountry(country: string | undefined) {
    this.defaultCountry$.next(country)
  }

  private getStoredUserSelectedLanguage(): string | undefined {
    return this.localStorageService.getString(this.languageStorageKey) || undefined
  }

  private getStoredUserSelectedCountry(): string | undefined {
    return this.localStorageService.getString(this.countryStorageKey) || undefined
  }

  private detectUserLocalizationViaAPI() {
    this.apiService.getLocalization().pipe(
      take(1),
    ).subscribe({
      next: (resp) => {
        this.detectedLanguage$.next(resp.language.recommended || undefined)
        this.detectedCountry$.next(resp.location.recommended || undefined)
        this.availableLanguages$.next(resp.language.available)
        this.availableCountries$.next(resp.location.available)
        this.translocoService.setAvailableLangs(resp.language.available)
      }
    })
  }

  private mustBePartOf(item: string | undefined, items: string[] ): string | undefined {
    if (item !== undefined && items.indexOf(item) !== -1) {
      return item
    }
    return undefined
  }
}
