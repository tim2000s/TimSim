package javax.inject

/** Stubs for the injection annotations, so the decision source compiles without Dagger. */
@Target(AnnotationTarget.CONSTRUCTOR, AnnotationTarget.FIELD, AnnotationTarget.FUNCTION)
annotation class Inject

@Target(AnnotationTarget.CLASS)
annotation class Singleton
