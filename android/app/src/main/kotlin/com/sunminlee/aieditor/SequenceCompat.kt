package com.sunminlee.aieditor

/** Small compatibility helper used by the programmatic UI skin. */
internal fun <T> Sequence<T>.isNotEmpty(): Boolean = iterator().hasNext()
