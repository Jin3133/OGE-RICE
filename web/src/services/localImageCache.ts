const DATABASE_NAME = 'oge-rice-local-assets'
const STORE_NAME = 'georeferencing-images'
const CURRENT_IMAGE_KEY = 'current-source-image'

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function saveGeoreferencingImage(file: File): Promise<void> {
  const db = await database()
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).put(file, CURRENT_IMAGE_KEY)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
  db.close()
}

export async function loadGeoreferencingImage(): Promise<File | null> {
  const db = await database()
  const value = await new Promise<File | null>((resolve, reject) => {
    const request = db.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(CURRENT_IMAGE_KEY)
    request.onsuccess = () => resolve(request.result instanceof File ? request.result : null)
    request.onerror = () => reject(request.error)
  })
  db.close()
  return value
}
